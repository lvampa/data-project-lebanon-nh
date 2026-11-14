from datetime import date, datetime
from unittest.mock import patch

from items import PoliceLogPdfItem, UrlRecordItem
from pipelines import UrlRecordPipeline
from postgres.models.pdf_url import PdfUrl
from sqlalchemy import select


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
    pipeline.open_spider()
    for item in items:
        pipeline.process_item(item)
    pipeline.close_spider()


def stored_urls(session) -> list[PdfUrl]:
    return session.scalars(select(PdfUrl).order_by(PdfUrl.canonical_url)).all()


def test_inserts_urls_once_and_ignores_existing(db_session):
    run_pipeline(
        make_item(canonical_url="https://example.com/a.pdf"),
        make_item(canonical_url="https://example.com/b.pdf"),
    )
    run_pipeline(
        make_item(canonical_url="https://example.com/b.pdf"),
        make_item(canonical_url="https://example.com/c.pdf"),
    )

    assert [url.canonical_url for url in stored_urls(db_session)] == [
        "https://example.com/a.pdf",
        "https://example.com/b.pdf",
        "https://example.com/c.pdf",
    ]


def test_inserts_archive_url_and_log_date(db_session):
    run_pipeline(
        make_item(
            archive_url="https://web.archive.org/web/2019/https://example.com/a.pdf",
            log_date=datetime(2026, 5, 1),
        )
    )

    [url] = stored_urls(db_session)
    assert url.archive_url is not None
    assert url.archive_url.startswith("https://web.archive.org/")
    assert url.log_date == date(2026, 5, 1)
    assert url.state == "pending"


@patch("pipelines.SessionLocal")
def test_passes_through_non_url_record_items(mock_session_local):
    pipeline = UrlRecordPipeline()
    pipeline.open_spider()
    item = PoliceLogPdfItem(url_id=1, raw_text="x")

    result = pipeline.process_item(item)
    pipeline.close_spider()

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
