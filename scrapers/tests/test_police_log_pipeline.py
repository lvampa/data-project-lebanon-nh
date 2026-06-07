from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from items import PoliceLogItem, UrlRecordItem
from pipelines import PoliceLogPipeline


def make_item(**kwargs):
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


@patch("pipelines.db")
@patch("pipelines.SessionLocal")
def test_pipeline_inserts_log_entry(mock_session_local, mock_db):
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    pipeline = PoliceLogPipeline()
    pipeline.open_spider(None)
    pipeline.process_item(make_item(), None)
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
