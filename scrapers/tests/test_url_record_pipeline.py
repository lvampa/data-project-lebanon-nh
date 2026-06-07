from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from items import PoliceLogItem, UrlRecordItem
from pipelines import UrlRecordPipeline


@patch("pipelines.db")
def test_pipeline_upserts_on_close(mock_db):
    pipeline = UrlRecordPipeline()
    pipeline.open_spider(None)
    now = datetime.now(timezone.utc)

    pipeline.process_item(
        UrlRecordItem(
            canonical_url="https://example.com/a.pdf", state="pending", created_at=now
        ),
        None,
    )
    pipeline.close_spider(None)

    mock_db.get_collection.assert_called_with("urls")
    ops = mock_db.get_collection.return_value.bulk_write.call_args[0][0]
    assert len(ops) == 1


@patch("pipelines.db")
def test_pipeline_passes_through_non_url_record_items(mock_db):
    pipeline = UrlRecordPipeline()
    pipeline.open_spider(None)
    item = PoliceLogItem(
        source_url="x", raw_text="x", scraped_at=datetime.now(timezone.utc)
    )

    result = pipeline.process_item(item, None)

    assert result is item
    pipeline.close_spider(None)
    mock_db.get_collection.return_value.bulk_write.assert_not_called()


@patch("pipelines.db")
def test_pipeline_skips_bulk_write_when_no_items(mock_db):
    pipeline = UrlRecordPipeline()
    pipeline.open_spider(None)
    pipeline.close_spider(None)
    mock_db.get_collection.return_value.bulk_write.assert_not_called()


def test_url_record_item_accepts_archive_url():
    item = UrlRecordItem(
        canonical_url="https://example.com/a.pdf",
        archive_url="https://web.archive.org/web/20191015/https://example.com/a.pdf",
        state="pending",
        created_at=datetime.now(timezone.utc),
    )
    assert (
        item["archive_url"]
        == "https://web.archive.org/web/20191015/https://example.com/a.pdf"
    )


@patch("pipelines.db")
def test_pipeline_upsert_includes_log_date(mock_db):
    from datetime import date

    pipeline = UrlRecordPipeline()
    pipeline.open_spider(None)
    now = datetime.now(timezone.utc)
    log_date = date(2026, 5, 1)

    pipeline.process_item(
        UrlRecordItem(
            canonical_url="https://example.com/a.pdf",
            log_date=log_date,
            state="pending",
            created_at=now,
        ),
        None,
    )
    pipeline.close_spider(None)

    ops = mock_db.get_collection.return_value.bulk_write.call_args[0][0]
    set_on_insert = ops[0]._doc["$setOnInsert"]
    assert set_on_insert["log_date"] == log_date
