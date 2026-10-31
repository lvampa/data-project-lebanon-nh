import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from bson import ObjectId
from items import PoliceLogItem, PoliceLogPdfItem
from scrapy.http import Request, Response
from spiders.process_url_records import CLAIM_LEASE, MAX_ATTEMPTS, ProcessUrlsSpider
from twisted.internet.error import DNSLookupError
from twisted.python.failure import Failure

FAKE_PDF = b"%PDF-1.4 fake pdf content"

SAMPLE_TEXT = """\
 Lebanon Police Department Page:   1
  Dispatch Log  From: 05/01/2026  Thru: 05/01/2026     0000 - 2359    Printed: 05/04/2026
For Date: 05/01/2026  -  Friday
Call   Number   Time   Call   Reason   Action
26-13339        0106 Phone - Telephone Harassment Incident Report Taken
       Call Source:    Telephone
        Primary Id:    SMN - Officer Stephan Nix
  Location/Address:    TIMBERWOOD DR
"""


def make_response(url: str, body: bytes) -> Response:
    return Response(url=url, body=body)


@patch("spiders.process_url_records.PdfReader")
@patch("spiders.process_url_records.db")
def test_parse_yields_police_log_items(mock_db, mock_pdf_reader):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = SAMPLE_TEXT
    mock_pdf_reader.return_value.pages = [mock_page]

    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.canonical_url = "https://example.com/a.pdf"
    url_doc.archive_url = None

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    items = list(spider.parse(response, url_doc=url_doc))

    assert len(items) == 1
    assert isinstance(items[0], PoliceLogPdfItem)
    assert items[0]["url_id"] is url_doc.id
    assert "26-13339" in items[0]["raw_text"]
    entries = items[0]["entries"]
    assert len(entries) == 1
    assert isinstance(entries[0], PoliceLogItem)
    assert entries[0]["source_url"] == "https://example.com/a.pdf"
    assert entries[0]["parse_error"] is False
    # raw_text is the per-entry block, not the full PDF text
    assert entries[0]["raw_text"].startswith("26-13339")


@patch("spiders.process_url_records.PdfReader")
@patch("spiders.process_url_records.db")
def test_parse_leaves_url_completion_to_pipeline(mock_db, mock_pdf_reader):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = SAMPLE_TEXT
    mock_pdf_reader.return_value.pages = [mock_page]

    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.canonical_url = "https://example.com/a.pdf"
    url_doc.archive_url = None

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    list(spider.parse(response, url_doc=url_doc))

    mock_db.get_collection.return_value.update_one.assert_not_called()


@patch("spiders.process_url_records.db")
def test_parse_non_pdf_with_archive_url_yields_fallback_request(mock_db):
    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.canonical_url = "https://example.com/a.pdf"
    url_doc.archive_url = (
        "https://web.archive.org/web/20191015/https://example.com/a.pdf"
    )

    response = make_response("https://example.com/a.pdf", b"<html>not a pdf</html>")
    results = list(spider.parse(response, url_doc=url_doc))

    assert len(results) == 1
    assert isinstance(results[0], Request)
    assert results[0].url == url_doc.archive_url


@patch("spiders.process_url_records.db")
def test_parse_non_pdf_without_archive_url_marks_mongo_error(mock_db):
    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.canonical_url = "https://example.com/a.pdf"
    url_doc.archive_url = None

    response = make_response("https://example.com/a.pdf", b"<html>not a pdf</html>")
    results = list(spider.parse(response, url_doc=url_doc))

    assert results == []
    update_call = mock_db.get_collection.return_value.update_one.call_args
    set_doc = update_call[0][1]["$set"]
    assert set_doc["state"] == "error"
    assert "error_message" in set_doc


@patch("spiders.process_url_records.PdfReader")
@patch("spiders.process_url_records.db")
def test_parse_no_entries_marks_mongo_error_and_yields_nothing(
    mock_db, mock_pdf_reader
):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "No date header here, will not parse"
    mock_pdf_reader.return_value.pages = [mock_page]

    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.canonical_url = "https://example.com/a.pdf"
    url_doc.archive_url = None

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    items = list(spider.parse(response, url_doc=url_doc))

    assert items == []
    update_call = mock_db.get_collection.return_value.update_one.call_args
    set_doc = update_call[0][1]["$set"]
    assert set_doc["state"] == "error"
    assert set_doc["entry_count"] == 0
    assert "error_message" in set_doc
    assert "raw_text" in set_doc


def _condition_holds(value: Any, condition: dict) -> bool:
    for op, arg in condition.items():
        if op == "$not":
            if _condition_holds(value, arg):
                return False
        elif op == "$gte":
            if value is None or value < arg:
                return False
        else:
            raise NotImplementedError(op)
    return True


def _matches(doc: dict, query: dict) -> bool:
    for field, condition in query.items():
        if isinstance(condition, dict):
            if not _condition_holds(doc.get(field), condition):
                return False
        elif doc.get(field) != condition:
            return False
    return True


class FakeUrls:
    """In-memory urls collection covering the query operators the spider uses."""

    def __init__(self, *docs: dict) -> None:
        self.docs = list(docs)

    def _apply(self, doc: dict, update: dict) -> None:
        doc.update(update.get("$set", {}))
        for field, amount in update.get("$inc", {}).items():
            doc[field] = doc.get(field, 0) + amount

    def update_many(self, query: dict, update: dict) -> MagicMock:
        matched = [doc for doc in self.docs if _matches(doc, query)]
        for doc in matched:
            self._apply(doc, update)
        return MagicMock(modified_count=len(matched))

    def update_one(self, query: dict, update: dict) -> None:
        for doc in self.docs:
            if _matches(doc, query):
                self._apply(doc, update)
                return

    def find_one_and_update(self, query: dict, update: dict) -> dict | None:
        for doc in self.docs:
            if _matches(doc, query):
                before = dict(doc)
                self._apply(doc, update)
                return before
        return None


def url_doc_row(**kwargs: Any) -> dict:
    row = {
        "_id": ObjectId(),
        "canonical_url": "https://example.com/a.pdf",
        "state": "pending",
        "created_at": datetime(2026, 5, 1),
    }
    row.update(kwargs)
    return row


def run_start(spider: ProcessUrlsSpider) -> list:
    async def collect() -> list:
        return [request async for request in spider.start()]

    return asyncio.run(collect())


def expired_claim_time() -> datetime:
    return datetime.now(UTC) - CLAIM_LEASE - timedelta(minutes=1)


@patch("spiders.process_url_records.db")
def test_claim_records_time_and_counts_attempt(mock_db):
    row = url_doc_row()
    mock_db.get_collection.return_value = FakeUrls(row)

    requests = run_start(ProcessUrlsSpider(limit=10))

    assert len(requests) == 1
    assert row["state"] == "in_progress"
    assert row["attempts"] == 1
    assert datetime.now(UTC) - row["claimed_at"] < timedelta(minutes=1)


@patch("spiders.process_url_records.db")
def test_stale_claim_is_retried(mock_db):
    stale = url_doc_row(
        state="in_progress", attempts=1, claimed_at=expired_claim_time()
    )
    legacy = url_doc_row(state="in_progress")
    fresh = url_doc_row(state="in_progress", attempts=1, claimed_at=datetime.now(UTC))
    mock_db.get_collection.return_value = FakeUrls(stale, legacy, fresh)

    requests = run_start(ProcessUrlsSpider(limit=10))

    assert len(requests) == 2
    assert stale["state"] == "in_progress"
    assert stale["attempts"] == 2
    assert legacy["state"] == "in_progress"
    assert legacy["attempts"] == 1
    assert fresh["attempts"] == 1


@patch("spiders.process_url_records.db")
def test_error_under_attempt_limit_is_retried(mock_db):
    row = url_doc_row(state="error", attempts=MAX_ATTEMPTS - 1)
    mock_db.get_collection.return_value = FakeUrls(row)

    requests = run_start(ProcessUrlsSpider(limit=10))

    assert len(requests) == 1
    assert row["state"] == "in_progress"
    assert row["attempts"] == MAX_ATTEMPTS


@patch("spiders.process_url_records.db")
def test_exhausted_attempts_stay_in_error(mock_db):
    errored = url_doc_row(state="error", attempts=MAX_ATTEMPTS)
    stale = url_doc_row(
        state="in_progress", attempts=MAX_ATTEMPTS, claimed_at=expired_claim_time()
    )
    mock_db.get_collection.return_value = FakeUrls(errored, stale)

    requests = run_start(ProcessUrlsSpider(limit=10))

    assert requests == []
    assert errored["state"] == "error"
    assert stale["state"] == "error"
    assert stale["attempts"] == MAX_ATTEMPTS


@patch("spiders.process_url_records.db")
def test_request_failure_marks_url_error(mock_db):
    row = url_doc_row()
    mock_db.get_collection.return_value = FakeUrls(row)
    [request] = run_start(ProcessUrlsSpider(limit=10))

    failure = Failure(DNSLookupError("no such host"))
    failure.request = request
    request.errback(failure)

    assert row["state"] == "error"
    assert "no such host" in row["error_message"]


@patch("spiders.process_url_records.db")
def test_archive_request_failure_marks_url_error(mock_db):
    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.archive_url = "https://web.archive.org/web/2019/https://example.com/a.pdf"

    response = make_response("https://example.com/a.pdf", b"<html>not a pdf</html>")
    [request] = list(spider.parse(response, url_doc=url_doc))
    failure = Failure(DNSLookupError("no such host"))
    failure.request = request
    request.errback(failure)

    set_doc = mock_db.get_collection.return_value.update_one.call_args[0][1]["$set"]
    assert set_doc["state"] == "error"


@patch("spiders.process_url_records.PdfReader")
@patch("spiders.process_url_records.db")
def test_unreadable_pdf_marks_url_error(mock_db, mock_pdf_reader):
    mock_pdf_reader.side_effect = ValueError("EOF marker not found")
    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    items = list(spider.parse(response, url_doc=url_doc))

    assert items == []
    set_doc = mock_db.get_collection.return_value.update_one.call_args[0][1]["$set"]
    assert set_doc["state"] == "error"
    assert "EOF marker not found" in set_doc["error_message"]
