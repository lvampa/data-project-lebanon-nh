import gzip
import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from items import PoliceLogPdfItem, UrlRecordItem
from mongo.archive import RawArchive
from parsers.police_log import PARSER_VERSION
from pipelines import PoliceLogPipeline
from postgres.models.log_entry import LogEntry
from postgres.models.pdf_url import PdfUrl
from pymongo.errors import OperationFailure
from scrapy.crawler import Crawler
from scrapy.settings import Settings
from spiders.process_url_records import ProcessUrlsSpider
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
    pipeline.open_spider()
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
    pipeline.open_spider()

    item = UrlRecordItem(
        canonical_url="x", state="pending", created_at=datetime.now(UTC)
    )
    result = pipeline.process_item(item)

    assert result is item
    mock_session_local.return_value.execute.assert_not_called()


def test_completes_url_with_its_entries(db_session):
    url_id = add_claimed_url(db_session)

    open_pipeline().process_item(make_pdf(url_id, "26-1001", "26-1002"))

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
        pipeline.process_item(make_pdf(url_id, "26-1001", "26-1002"))

    assert stored_case_numbers(db_session) == []
    url = stored_url(db_session, url_id)
    assert (url.state, url.error_kind) == ("error", "save")
    assert url.error_message is not None and "database error" in url.error_message


def test_a_save_error_is_downloaded_again_when_the_original_is_not_archived(
    db_session, monkeypatch
):
    url_id = add_claimed_url(db_session)
    pipeline = open_pipeline()
    monkeypatch.setattr(
        "pipelines.ingest_pdf_url", MagicMock(side_effect=RuntimeError("bad pdf"))
    )

    with pytest.raises(RuntimeError):
        pipeline.process_item(make_pdf(url_id, "26-1001", original_archived=False))

    assert stored_url(db_session, url_id).error_kind == "download"


def test_first_pdf_stays_committed_when_second_fails(db_session, monkeypatch):
    first_url = add_claimed_url(db_session, "https://example.com/a.pdf")
    second_url = add_claimed_url(db_session, "https://example.com/b.pdf")
    pipeline = open_pipeline()

    pipeline.process_item(make_pdf(first_url, "26-1001"))
    monkeypatch.setattr(
        "pipelines.ingest_pdf_url", MagicMock(side_effect=RuntimeError("bad pdf"))
    )
    with pytest.raises(RuntimeError):
        pipeline.process_item(make_pdf(second_url, "26-1002"))
    pipeline.close_spider()

    assert stored_case_numbers(db_session) == ["26-1001"]
    assert stored_url(db_session, first_url).state == "complete"
    assert stored_url(db_session, second_url).error_kind == "save"


def test_same_case_number_twice_gives_one_row(db_session):
    first_url = add_claimed_url(db_session, "https://example.com/a.pdf")
    second_url = add_claimed_url(db_session, "https://example.com/b.pdf")
    pipeline = open_pipeline()

    pipeline.process_item(make_pdf(first_url, "26-1001"))
    pipeline.process_item(make_pdf(second_url, "26-1001"))

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
        )
    )

    url = stored_url(db_session, url_id)
    assert (url.state, url.error_kind) == ("error", "parse")


# --- entry texts in the raw archive ---


def archiving_pipeline(collection) -> PoliceLogPipeline:
    pipeline = PoliceLogPipeline(RawArchive(collection))
    pipeline.open_spider()
    return pipeline


def entry_texts(raw_sources) -> list[dict]:
    return list(
        raw_sources.find({"source": "police_log_entry_text"}).sort("source_key", 1)
    )


def test_each_entry_text_is_archived_after_the_commit(db_session, raw_sources):
    url_id = add_claimed_url(db_session)

    archiving_pipeline(raw_sources).process_item(make_pdf(url_id, "26-1001", "26-1002"))

    versions = entry_texts(raw_sources)
    assert [v["source_key"] for v in versions] == ["26-1001", "26-1002"]
    body = json.loads(gzip.decompress(versions[0]["body_gzip"]))
    assert body == {
        "raw_text": entry_text("26-1001").strip(),
        "raw_reason_action": "Noise Complaint Log Information",
        "source_url": "https://example.com/a.pdf",
        "parser_version": PARSER_VERSION,
    }
    assert versions[0]["spider"] == "process_urls"


def test_the_same_parse_again_only_moves_the_seen_count(db_session, raw_sources):
    url_id = add_claimed_url(db_session)
    pipeline = archiving_pipeline(raw_sources)

    pipeline.process_item(make_pdf(url_id, "26-1001"))
    pipeline.process_item(make_pdf(url_id, "26-1001"))

    [version] = entry_texts(raw_sources)
    assert version["seen_count"] == 2


def test_a_parser_bump_stores_a_new_entry_text_version(
    db_session, raw_sources, monkeypatch
):
    url_id = add_claimed_url(db_session)
    pipeline = archiving_pipeline(raw_sources)
    pipeline.process_item(make_pdf(url_id, "26-1001"))

    monkeypatch.setattr("ingest.police_log.PARSER_VERSION", PARSER_VERSION + 1)
    pipeline.process_item(make_pdf(url_id, "26-1001"))

    assert len(entry_texts(raw_sources)) == 2


class FailingCollection:
    """A collection whose writes fail, as on a full disk."""

    def bulk_write(self, operations, ordered: bool):
        raise OperationFailure("disk full")


def test_a_failed_entry_text_write_keeps_the_entries(db_session):
    url_id = add_claimed_url(db_session)

    archiving_pipeline(FailingCollection()).process_item(make_pdf(url_id, "26-1001"))

    assert stored_case_numbers(db_session) == ["26-1001"]
    assert stored_url(db_session, url_id).state == "complete"


def test_no_entry_texts_are_archived_while_the_archive_is_off(db_session, raw_sources):
    crawler = SimpleNamespace(
        settings=Settings({"RAW_ARCHIVE_ENABLED": False}), spidercls=ProcessUrlsSpider
    )
    pipeline = PoliceLogPipeline.from_crawler(cast(Crawler, crawler))
    pipeline.open_spider()

    pipeline.process_item(make_pdf(add_claimed_url(db_session), "26-1001"))

    assert entry_texts(raw_sources) == []
