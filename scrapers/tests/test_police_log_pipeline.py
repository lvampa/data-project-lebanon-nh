from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest
from items import PoliceLogPdfItem, UrlRecordItem
from pipelines import PoliceLogPipeline
from postgres.models.log_entry import LogEntry
from postgres.models.pdf_url import PdfUrl
from sqlalchemy import select

HEADER = """\
For Date: 05/11/2026  -  Monday
Call   Number   Time   Call   Reason   Action
"""


def entry_text(case_number: str) -> str:
    return (
        f"{case_number}        0106 Phone - Noise Complaint Log Information\n"
        "       Call Source:    Telephone\n"
        "  Location/Address:    MAIN ST\n"
    )


def make_pdf(
    url_id: int, *case_numbers: str, original_archived: bool = True
) -> PoliceLogPdfItem:
    text = HEADER + "".join(entry_text(case_number) for case_number in case_numbers)
    return PoliceLogPdfItem(
        url_id=url_id,
        raw_text=text,
        content_hash="ab" * 32,
        original_archived=original_archived,
    )


def add_claimed_url(session, canonical_url="https://example.com/a.pdf") -> int:
    url = PdfUrl(
        canonical_url=canonical_url,
        log_date=date(2026, 5, 11),
        state="in_progress",
        attempts=1,
        created_at=datetime(2026, 5, 12),
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


def stored_url(session, url_id: int) -> PdfUrl:
    session.expire_all()
    return session.get(PdfUrl, url_id)


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

    open_pipeline().process_item(make_pdf(url_id, "26-1001", "26-1002"), None)

    assert stored_case_numbers(db_session) == ["26-1001", "26-1002"]
    url = stored_url(db_session, url_id)
    assert url.state == "complete"
    assert (url.parsed_count, url.stored_count) == (2, 2)
    assert url.content_hash == "ab" * 32
    assert url.completed_at is not None


def test_entries_are_not_stored_when_the_commit_fails(db_session, monkeypatch):
    url_id = add_claimed_url(db_session)
    pipeline = open_pipeline()
    real_commit = pipeline._session.commit

    def fail_once():
        # Only the commit that carries the entries and the completed URL fails.
        monkeypatch.setattr(pipeline._session, "commit", real_commit)
        raise RuntimeError("database error")

    monkeypatch.setattr(pipeline._session, "commit", fail_once)

    with pytest.raises(RuntimeError):
        pipeline.process_item(make_pdf(url_id, "26-1001", "26-1002"), None)

    assert stored_case_numbers(db_session) == []
    url = stored_url(db_session, url_id)
    assert (url.state, url.error_kind) == ("error", "save")
    assert "database error" in url.error_message


def test_a_save_error_is_downloaded_again_when_the_original_is_not_archived(
    db_session, monkeypatch
):
    url_id = add_claimed_url(db_session)
    pipeline = open_pipeline()
    monkeypatch.setattr(
        "pipelines.ingest_pdf_url", MagicMock(side_effect=RuntimeError("bad pdf"))
    )

    with pytest.raises(RuntimeError):
        pipeline.process_item(
            make_pdf(url_id, "26-1001", original_archived=False), None
        )

    assert stored_url(db_session, url_id).error_kind == "download"


def test_first_pdf_stays_committed_when_second_fails(db_session, monkeypatch):
    first_url = add_claimed_url(db_session, "https://example.com/a.pdf")
    second_url = add_claimed_url(db_session, "https://example.com/b.pdf")
    pipeline = open_pipeline()

    pipeline.process_item(make_pdf(first_url, "26-1001"), None)
    monkeypatch.setattr(
        "pipelines.ingest_pdf_url", MagicMock(side_effect=RuntimeError("bad pdf"))
    )
    with pytest.raises(RuntimeError):
        pipeline.process_item(make_pdf(second_url, "26-1002"), None)
    pipeline.close_spider(None)

    assert stored_case_numbers(db_session) == ["26-1001"]
    assert stored_url(db_session, first_url).state == "complete"
    assert stored_url(db_session, second_url).error_kind == "save"


def test_same_case_number_twice_gives_one_row(db_session):
    first_url = add_claimed_url(db_session, "https://example.com/a.pdf")
    second_url = add_claimed_url(db_session, "https://example.com/b.pdf")
    pipeline = open_pipeline()

    pipeline.process_item(make_pdf(first_url, "26-1001"), None)
    pipeline.process_item(make_pdf(second_url, "26-1001"), None)

    assert stored_case_numbers(db_session) == ["26-1001"]
    assert stored_url(db_session, second_url).state == "complete"


def test_pdf_with_no_entries_becomes_a_parse_error(db_session):
    url_id = add_claimed_url(db_session)

    open_pipeline().process_item(
        PoliceLogPdfItem(
            url_id=url_id,
            raw_text="not a police log",
            content_hash="cd" * 32,
            original_archived=True,
        ),
        None,
    )

    url = stored_url(db_session, url_id)
    assert (url.state, url.error_kind) == ("error", "parse")
