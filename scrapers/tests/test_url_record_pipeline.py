from datetime import date, datetime
from unittest.mock import patch

from items import PoliceLogItem, UrlRecordItem
from pipelines import UrlRecordPipeline
from sqlalchemy.dialects import postgresql


def make_item(**kwargs) -> UrlRecordItem:
    defaults = {
        "canonical_url": "https://example.com/a.pdf",
        "state": "pending",
        "created_at": datetime(2026, 5, 1, 12, 0),
    }
    defaults.update(kwargs)
    return UrlRecordItem(**defaults)


def run_pipeline(*items) -> None:
    pipeline = UrlRecordPipeline()
    pipeline.open_spider(None)
    for item in items:
        pipeline.process_item(item, None)
    pipeline.close_spider(None)


def compile_pg(statement):
    return statement.compile(dialect=postgresql.dialect())


@patch("pipelines.SessionLocal")
def test_inserts_urls_once_and_ignores_existing(mock_session_local, fake_session):
    mock_session_local.return_value = fake_session

    run_pipeline(
        make_item(canonical_url="https://example.com/a.pdf"),
        make_item(canonical_url="https://example.com/b.pdf"),
    )

    [[statement]] = fake_session.transactions
    compiled = compile_pg(statement)
    assert "INSERT INTO pdf_urls" in str(compiled)
    assert "ON CONFLICT (canonical_url) DO NOTHING" in str(compiled)
    assert compiled.params["canonical_url_m0"] == "https://example.com/a.pdf"
    assert compiled.params["canonical_url_m1"] == "https://example.com/b.pdf"


@patch("pipelines.SessionLocal")
def test_inserts_archive_url_and_log_date(mock_session_local, fake_session):
    mock_session_local.return_value = fake_session

    run_pipeline(
        make_item(
            archive_url="https://web.archive.org/web/2019/https://example.com/a.pdf",
            log_date=datetime(2026, 5, 1),
        )
    )

    params = compile_pg(fake_session.committed[0]).params
    assert params["archive_url_m0"].startswith("https://web.archive.org/")
    assert params["log_date_m0"] == date(2026, 5, 1)
    assert params["state_m0"] == "pending"


@patch("pipelines.SessionLocal")
def test_passes_through_non_url_record_items(mock_session_local):
    pipeline = UrlRecordPipeline()
    pipeline.open_spider(None)
    item = PoliceLogItem(source_url="x", raw_text="x", scraped_at=datetime(2026, 5, 1))

    result = pipeline.process_item(item, None)
    pipeline.close_spider(None)

    assert result is item
    mock_session_local.assert_not_called()


@patch("pipelines.SessionLocal")
def test_opens_no_session_when_no_items(mock_session_local):
    run_pipeline()

    mock_session_local.assert_not_called()


def test_url_record_item_accepts_archive_url():
    item = make_item(
        archive_url="https://web.archive.org/web/20191015/https://example.com/a.pdf"
    )
    assert (
        item["archive_url"]
        == "https://web.archive.org/web/20191015/https://example.com/a.pdf"
    )
