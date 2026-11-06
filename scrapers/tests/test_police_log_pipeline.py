from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
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


def make_pdf(*entries, url_id=None):
    return PoliceLogPdfItem(
        url_id=url_id or ObjectId(),
        raw_text="full pdf text",
        entries=list(entries) or [make_entry()],
    )


def _case_number(statement) -> str:
    return statement.compile(dialect=postgresql.dialect()).params["case_number"]


def _url_update(mock_db):
    filter_doc, update_doc = mock_db.get_collection.return_value.update_one.call_args[0]
    return filter_doc, update_doc["$set"]


@patch("pipelines.db")
@patch("pipelines.SessionLocal")
def test_pipeline_inserts_log_entry(mock_session_local, mock_db):
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    pipeline = PoliceLogPipeline()
    pipeline.open_spider(None)
    pipeline.process_item(make_pdf(), None)
    pipeline.close_spider(None)

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


@patch("pipelines.db")
@patch("pipelines.SessionLocal")
def test_pipeline_passes_through_non_police_log_items(mock_session_local, mock_db):
    mock_session_local.return_value = MagicMock()

    pipeline = PoliceLogPipeline()
    pipeline.open_spider(None)

    item = UrlRecordItem(
        canonical_url="x", state="pending", created_at=datetime.now(UTC)
    )
    result = pipeline.process_item(item, None)

    assert result is item
    mock_session_local.return_value.execute.assert_not_called()


@patch("pipelines.db")
def test_first_pdf_stays_committed_when_second_fails(mock_db, fake_session):
    pipeline = PoliceLogPipeline()
    pipeline._session = fake_session
    fake_session.fail_on_call = 2

    pipeline.process_item(make_pdf(make_entry(case_number="2024-1001")), None)
    with pytest.raises(RuntimeError):
        pipeline.process_item(make_pdf(make_entry(case_number="2024-1002")), None)
    pipeline.close_spider(None)

    assert [_case_number(s) for s in fake_session.committed] == ["2024-1001"]


@patch("pipelines.db")
def test_marks_url_complete_only_after_entries_commit(mock_db, fake_session):
    pipeline = PoliceLogPipeline()
    pipeline._session = fake_session
    url_id = ObjectId()
    committed_when_marked = []
    mock_db.get_collection.return_value.update_one.side_effect = lambda *args: (
        committed_when_marked.append(len(fake_session.committed))
    )

    pipeline.process_item(
        make_pdf(
            make_entry(case_number="2024-1001"),
            make_entry(case_number="2024-1002"),
            url_id=url_id,
        ),
        None,
    )

    assert committed_when_marked == [2]
    filter_doc, set_doc = _url_update(mock_db)
    assert filter_doc == {"_id": url_id}
    assert set_doc["state"] == "complete"
    assert set_doc["entry_count"] == 2
    assert set_doc["raw_text"] == "full pdf text"
    assert "completed_at" in set_doc


@patch("pipelines.db")
def test_failed_entry_rolls_back_pdf_and_marks_url_error(mock_db, fake_session):
    pipeline = PoliceLogPipeline()
    pipeline._session = fake_session
    fake_session.fail_on_call = 2
    url_id = ObjectId()

    with pytest.raises(RuntimeError):
        pipeline.process_item(
            make_pdf(
                make_entry(case_number="2024-1001"),
                make_entry(case_number="2024-1002"),
                url_id=url_id,
            ),
            None,
        )

    assert fake_session.committed == []
    filter_doc, set_doc = _url_update(mock_db)
    assert filter_doc == {"_id": url_id}
    assert set_doc["state"] == "error"
    assert "database error" in set_doc["error_message"]
