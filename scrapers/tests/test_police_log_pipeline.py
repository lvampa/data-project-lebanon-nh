from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from items import PoliceLogItem, PoliceLogPdfItem, UrlRecordItem
from pipelines import PoliceLogPipeline
from sqlalchemy.dialects import postgresql


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


def make_pipeline(session) -> PoliceLogPipeline:
    pipeline = PoliceLogPipeline()
    pipeline._session = session
    return pipeline


def compile_pg(statement):
    return statement.compile(dialect=postgresql.dialect())


def is_entry_insert(statement) -> bool:
    return str(compile_pg(statement)).startswith("INSERT INTO log_entries")


def is_url_update(statement) -> bool:
    return str(compile_pg(statement)).startswith("UPDATE pdf_urls")


def committed_case_numbers(session) -> list[str]:
    return [
        compile_pg(s).params["case_number"]
        for s in session.committed
        if is_entry_insert(s)
    ]


@patch("pipelines.SessionLocal")
def test_pipeline_opens_session_and_commits(mock_session_local):
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    pipeline = PoliceLogPipeline()
    pipeline.open_spider()
    pipeline.process_item(make_pdf())
    pipeline.close_spider()

    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


@patch("pipelines.SessionLocal")
def test_pipeline_passes_through_non_police_log_items(mock_session_local):
    mock_session_local.return_value = MagicMock()

    pipeline = PoliceLogPipeline()
    pipeline.open_spider()

    item = UrlRecordItem(
        canonical_url="x", state="pending", created_at=datetime.now(UTC)
    )
    result = pipeline.process_item(item)

    assert result is item
    mock_session_local.return_value.execute.assert_not_called()


def test_completes_url_in_same_transaction_as_entries(fake_session):
    pipeline = make_pipeline(fake_session)

    pipeline.process_item(
        make_pdf(
            make_entry(case_number="2024-1001"),
            make_entry(case_number="2024-1002"),
            url_id=7,
        )
    )

    [transaction] = fake_session.transactions
    *entry_inserts, url_update = transaction
    assert [compile_pg(s).params["case_number"] for s in entry_inserts] == [
        "2024-1001",
        "2024-1002",
    ]
    assert is_url_update(url_update)
    values = compile_pg(url_update).params
    assert values["id_1"] == 7
    assert values["state"] == "complete"
    assert values["entry_count"] == 2
    assert values["raw_text"] == "full pdf text"
    assert values["completed_at"].tzinfo is None


def test_first_pdf_stays_committed_when_second_fails(fake_session):
    pipeline = make_pipeline(fake_session)
    # Calls 1 and 2 are the first PDF's entry and URL update; call 3 is the second entry.
    fake_session.fail_on_call = 3

    pipeline.process_item(make_pdf(make_entry(case_number="2024-1001")))
    with pytest.raises(RuntimeError):
        pipeline.process_item(make_pdf(make_entry(case_number="2024-1002")))
    pipeline.close_spider()

    assert committed_case_numbers(fake_session) == ["2024-1001"]


def test_failed_entry_rolls_back_pdf_and_marks_url_error(fake_session):
    pipeline = make_pipeline(fake_session)
    fake_session.fail_on_call = 2

    with pytest.raises(RuntimeError):
        pipeline.process_item(
            make_pdf(
                make_entry(case_number="2024-1001"),
                make_entry(case_number="2024-1002"),
                url_id=7,
            )
        )

    [[url_update]] = fake_session.transactions
    assert is_url_update(url_update)
    values = compile_pg(url_update).params
    assert values["id_1"] == 7
    assert values["state"] == "error"
    assert "database error" in values["error_message"]
