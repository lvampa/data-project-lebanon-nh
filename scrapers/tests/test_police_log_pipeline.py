from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from items import PoliceLogItem, PoliceLogPdfItem, UrlRecordItem
from pipelines import PoliceLogPipeline
from postgres.models.log_entry import LogEntry
from postgres.models.pdf_url import PdfUrl
from sqlalchemy import select


def make_entry(**kwargs):
    defaults = {
        "source_url": "https://example.com/a.pdf",
        "raw_text": "some text",
        "scraped_at": datetime.now(UTC),
        "case_number": "2024-1001",
        "reported_at": datetime(2024, 3, 15, 8, 32),
        "incident_type": "MV STOP",
        "location": "N MAIN ST",
        "officer": "Jones",
        "disposition": "WARNING",
        "parse_error": False,
    }
    defaults.update(kwargs)
    return PoliceLogItem(**defaults)


def make_pdf(*entries, url_id=7):
    return PoliceLogPdfItem(
        url_id=url_id,
        raw_text="full pdf text",
        entries=list(entries) or [make_entry()],
    )


def add_claimed_url(session, canonical_url="https://example.com/a.pdf") -> int:
    url = PdfUrl(
        canonical_url=canonical_url,
        state="in_progress",
        attempts=1,
        created_at=datetime(2024, 3, 16),
    )
    session.add(url)
    session.commit()
    return url.id


def open_pipeline() -> PoliceLogPipeline:
    pipeline = PoliceLogPipeline()
    pipeline.open_spider(None)
    return pipeline


def stored_case_numbers(session) -> list[str]:
    return session.scalars(
        select(LogEntry.case_number).order_by(LogEntry.case_number)
    ).all()


@patch("pipelines.SessionLocal")
def test_pipeline_passes_through_non_police_log_items(mock_session_local):
    mock_session_local.return_value = MagicMock()

    pipeline = PoliceLogPipeline()
    pipeline.open_spider(None)

    item = UrlRecordItem(
        canonical_url="x", state="pending", created_at=datetime.now(UTC)
    )
    result = pipeline.process_item(item, None)

    assert result is item
    mock_session_local.return_value.execute.assert_not_called()


def test_completes_url_with_its_entries(db_session):
    url_id = add_claimed_url(db_session)

    open_pipeline().process_item(
        make_pdf(
            make_entry(case_number="2024-1001"),
            make_entry(case_number="2024-1002"),
            url_id=url_id,
        ),
        None,
    )

    assert stored_case_numbers(db_session) == ["2024-1001", "2024-1002"]
    url = db_session.get(PdfUrl, url_id)
    assert url.state == "complete"
    assert url.entry_count == 2
    assert url.raw_text == "full pdf text"
    assert url.completed_at is not None


def test_entries_are_not_stored_when_completing_the_url_fails(
    db_session, fail_on_execute
):
    url_id = add_claimed_url(db_session)
    pipeline = open_pipeline()
    # Calls 1 and 2 insert the entries; call 3 is the update that completes the URL.
    fail_on_execute(pipeline._session, 3)

    with pytest.raises(RuntimeError):
        pipeline.process_item(
            make_pdf(
                make_entry(case_number="2024-1001"),
                make_entry(case_number="2024-1002"),
                url_id=url_id,
            ),
            None,
        )

    assert stored_case_numbers(db_session) == []
    assert db_session.get(PdfUrl, url_id).state == "error"


def test_first_pdf_stays_committed_when_second_fails(db_session, fail_on_execute):
    first_url = add_claimed_url(db_session, "https://example.com/a.pdf")
    second_url = add_claimed_url(db_session, "https://example.com/b.pdf")
    pipeline = open_pipeline()
    # Calls 1 and 2 are the first PDF's entry and URL update; call 3 is the second entry.
    fail_on_execute(pipeline._session, 3)

    pipeline.process_item(
        make_pdf(make_entry(case_number="2024-1001"), url_id=first_url), None
    )
    with pytest.raises(RuntimeError):
        pipeline.process_item(
            make_pdf(make_entry(case_number="2024-1002"), url_id=second_url), None
        )
    pipeline.close_spider(None)

    assert stored_case_numbers(db_session) == ["2024-1001"]
    assert db_session.get(PdfUrl, first_url).state == "complete"


def test_failed_entry_rolls_back_pdf_and_marks_url_error(db_session, fail_on_execute):
    url_id = add_claimed_url(db_session)
    pipeline = open_pipeline()
    fail_on_execute(pipeline._session, 2)

    with pytest.raises(RuntimeError):
        pipeline.process_item(
            make_pdf(
                make_entry(case_number="2024-1001"),
                make_entry(case_number="2024-1002"),
                url_id=url_id,
            ),
            None,
        )

    assert stored_case_numbers(db_session) == []
    url = db_session.get(PdfUrl, url_id)
    assert url.state == "error"
    assert "database error" in url.error_message


def test_same_case_number_twice_gives_one_row(db_session):
    first_url = add_claimed_url(db_session, "https://example.com/a.pdf")
    second_url = add_claimed_url(db_session, "https://example.com/b.pdf")
    pipeline = open_pipeline()

    pipeline.process_item(
        make_pdf(make_entry(case_number="2024-1001"), url_id=first_url), None
    )
    pipeline.process_item(
        make_pdf(make_entry(case_number="2024-1001"), url_id=second_url), None
    )

    assert stored_case_numbers(db_session) == ["2024-1001"]
    assert db_session.get(PdfUrl, second_url).state == "complete"
