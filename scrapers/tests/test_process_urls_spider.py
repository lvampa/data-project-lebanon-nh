import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from items import PoliceLogItem, PoliceLogPdfItem
from models import PdfUrlClaim
from postgres.models.pdf_url import PdfUrl
from scrapy.http import Request, Response
from spiders.process_url_records import (
    CLAIM_LEASE,
    MAX_ATTEMPTS,
    ProcessUrlsSpider,
    claim_statement,
)
from sqlalchemy import Table, create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
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

ARCHIVE_URL = "https://web.archive.org/web/20191015/https://example.com/a.pdf"


def make_response(url: str, body: bytes) -> Response:
    return Response(url=url, body=body)


def make_claim(**kwargs: Any) -> PdfUrlClaim:
    defaults = {"id": 7, "canonical_url": "https://example.com/a.pdf"}
    defaults.update(kwargs)
    return PdfUrlClaim(**defaults)


def make_spider() -> ProcessUrlsSpider:
    return ProcessUrlsSpider.__new__(ProcessUrlsSpider)


def url_update_values(statement) -> dict:
    compiled = statement.compile(dialect=postgresql.dialect())
    assert str(compiled).startswith("UPDATE pdf_urls SET")
    return compiled.params


@pytest.fixture
def session_local(fake_session):
    with patch("spiders.process_url_records.SessionLocal") as mock_session_local:
        mock_session_local.return_value = fake_session
        yield mock_session_local


@pytest.fixture
def pdf_reader():
    with patch("spiders.process_url_records.PdfReader") as mock_pdf_reader:
        yield mock_pdf_reader


def pdf_with_text(pdf_reader, text: str) -> None:
    page = MagicMock()
    page.extract_text.return_value = text
    pdf_reader.return_value.pages = [page]


# --- parse ---


def test_parse_yields_police_log_items(session_local, pdf_reader):
    pdf_with_text(pdf_reader, SAMPLE_TEXT)
    pdf_url = make_claim()

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    items = list(make_spider().parse(response, pdf_url=pdf_url))

    assert len(items) == 1
    assert isinstance(items[0], PoliceLogPdfItem)
    assert items[0]["url_id"] == pdf_url.id
    assert "26-13339" in items[0]["raw_text"]
    entries = items[0]["entries"]
    assert len(entries) == 1
    assert isinstance(entries[0], PoliceLogItem)
    assert entries[0]["source_url"] == "https://example.com/a.pdf"
    assert entries[0]["parse_error"] is False
    # raw_text is the per-entry block, not the full PDF text
    assert entries[0]["raw_text"].startswith("26-13339")
    # log_entries.scraped_at is a naive UTC column, like every other writer uses.
    assert entries[0]["scraped_at"].tzinfo is None


def test_parse_leaves_url_completion_to_pipeline(session_local, pdf_reader):
    pdf_with_text(pdf_reader, SAMPLE_TEXT)

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    list(make_spider().parse(response, pdf_url=make_claim()))

    session_local.assert_not_called()


def test_parse_non_pdf_with_archive_url_yields_fallback_request(session_local):
    response = make_response("https://example.com/a.pdf", b"<html>not a pdf</html>")
    results = list(
        make_spider().parse(response, pdf_url=make_claim(archive_url=ARCHIVE_URL))
    )

    assert len(results) == 1
    assert isinstance(results[0], Request)
    assert results[0].url == ARCHIVE_URL


def test_parse_non_pdf_without_archive_url_marks_url_error(session_local, fake_session):
    response = make_response("https://example.com/a.pdf", b"<html>not a pdf</html>")
    results = list(make_spider().parse(response, pdf_url=make_claim()))

    assert results == []
    [statement] = fake_session.committed
    values = url_update_values(statement)
    assert values["id_1"] == 7
    assert values["state"] == "error"
    assert "no archive URL" in values["error_message"]


def test_parse_no_entries_marks_url_error_and_yields_nothing(
    session_local, fake_session, pdf_reader
):
    pdf_with_text(pdf_reader, "No date header here, will not parse")

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    items = list(make_spider().parse(response, pdf_url=make_claim()))

    assert items == []
    [statement] = fake_session.committed
    values = url_update_values(statement)
    assert values["state"] == "error"
    assert values["entry_count"] == 0
    assert values["error_message"] == "No entries parsed from PDF"
    assert values["raw_text"] == "No date header here, will not parse"


def test_archive_request_failure_marks_url_error(session_local, fake_session):
    response = make_response("https://example.com/a.pdf", b"<html>not a pdf</html>")
    [request] = list(
        make_spider().parse(response, pdf_url=make_claim(archive_url=ARCHIVE_URL))
    )
    assert isinstance(request, Request)
    assert request.errback is not None
    failure = Failure(DNSLookupError("no such host"))
    # Scrapy sets `request` on the Failure it passes to an errback; Twisted's
    # types do not declare it.
    # pyrefly: ignore[missing-attribute]
    failure.request = request
    request.errback(failure)

    [statement] = fake_session.committed
    assert url_update_values(statement)["state"] == "error"


def test_unreadable_pdf_marks_url_error(session_local, fake_session, pdf_reader):
    pdf_reader.side_effect = ValueError("EOF marker not found")

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    items = list(make_spider().parse(response, pdf_url=make_claim()))

    assert items == []
    [statement] = fake_session.committed
    values = url_update_values(statement)
    assert values["state"] == "error"
    assert "EOF marker not found" in values["error_message"]


# --- claim statement ---


def test_claim_skips_rows_locked_by_other_runs():
    now = datetime(2026, 5, 1, 12, 0)
    sql = " ".join(
        str(claim_statement(10, now).compile(dialect=postgresql.dialect())).split()
    )

    assert "FOR UPDATE SKIP LOCKED" in sql
    assert (
        "WHERE pdf_urls.id IN (SELECT pdf_urls.id FROM pdf_urls WHERE pdf_urls.state"
        in sql
    )
    assert "ORDER BY pdf_urls.created_at LIMIT" in sql
    assert "attempts=(pdf_urls.attempts +" in sql
    assert "RETURNING pdf_urls.id, pdf_urls.canonical_url, pdf_urls.archive_url" in sql


# --- start: requeue and claim against a real pdf_urls table ---


def test_limit_from_the_command_line_is_read_as_a_number():
    # `scrapy crawl process_urls -a limit=3` passes the limit as a string.
    assert ProcessUrlsSpider(limit="3").limit == 3


@pytest.fixture
def queue_db():
    # SQLite runs the same UPDATE ... RETURNING statements and ignores FOR UPDATE,
    # which is covered by the compiled-statement test above.
    engine = create_engine("sqlite://", poolclass=StaticPool)
    cast(Table, PdfUrl.__table__).create(engine)
    session_factory = sessionmaker(bind=engine)
    with patch("spiders.process_url_records.SessionLocal", session_factory):
        yield session_factory
    engine.dispose()


def add_url(session_factory: sessionmaker[Session], **kwargs: Any) -> int:
    defaults = {
        "canonical_url": f"https://example.com/{kwargs.get('created_at', '')}.pdf",
        "state": "pending",
        "created_at": datetime(2026, 5, 1),
    }
    defaults.update(kwargs)
    with session_factory() as session:
        row = PdfUrl(**defaults)
        session.add(row)
        session.commit()
        return row.id


def get_url(session_factory: sessionmaker[Session], url_id: int) -> PdfUrl:
    with session_factory() as session:
        return session.scalars(select(PdfUrl).where(PdfUrl.id == url_id)).one()


def run_start(spider: ProcessUrlsSpider) -> list:
    async def collect() -> list:
        return [request async for request in spider.start()]

    return asyncio.run(collect())


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def expired_claim_time() -> datetime:
    return utc_now() - CLAIM_LEASE - timedelta(minutes=1)


def test_claim_records_time_and_counts_attempt(queue_db):
    url_id = add_url(queue_db)

    [request] = run_start(ProcessUrlsSpider(limit=10))

    row = get_url(queue_db, url_id)
    assert request.url == row.canonical_url
    assert request.cb_kwargs["pdf_url"].id == url_id
    assert row.state == "in_progress"
    assert row.attempts == 1
    assert row.claimed_at is not None
    assert utc_now() - row.claimed_at < timedelta(minutes=1)


def test_claims_oldest_first_up_to_limit(queue_db):
    newest = add_url(queue_db, created_at=datetime(2026, 5, 3))
    oldest = add_url(queue_db, created_at=datetime(2026, 5, 1))
    middle = add_url(queue_db, created_at=datetime(2026, 5, 2))

    requests = run_start(ProcessUrlsSpider(limit=2))

    claimed = {request.cb_kwargs["pdf_url"].id for request in requests}
    assert claimed == {oldest, middle}
    assert get_url(queue_db, newest).state == "pending"


def test_no_pending_urls_yields_no_requests(queue_db):
    add_url(queue_db, state="complete")

    assert run_start(ProcessUrlsSpider(limit=10)) == []


def test_stale_claim_is_retried(queue_db):
    stale = add_url(
        queue_db,
        canonical_url="https://example.com/stale.pdf",
        state="in_progress",
        attempts=1,
        claimed_at=expired_claim_time(),
    )
    fresh = add_url(
        queue_db,
        canonical_url="https://example.com/fresh.pdf",
        state="in_progress",
        attempts=1,
        claimed_at=utc_now(),
    )

    requests = run_start(ProcessUrlsSpider(limit=10))

    assert [request.cb_kwargs["pdf_url"].id for request in requests] == [stale]
    assert get_url(queue_db, stale).state == "in_progress"
    assert get_url(queue_db, stale).attempts == 2
    assert get_url(queue_db, fresh).attempts == 1


def test_error_under_attempt_limit_is_retried(queue_db):
    url_id = add_url(queue_db, state="error", attempts=MAX_ATTEMPTS - 1)

    requests = run_start(ProcessUrlsSpider(limit=10))

    row = get_url(queue_db, url_id)
    assert len(requests) == 1
    assert row.state == "in_progress"
    assert row.attempts == MAX_ATTEMPTS


def test_exhausted_attempts_stay_in_error(queue_db):
    errored = add_url(
        queue_db,
        canonical_url="https://example.com/errored.pdf",
        state="error",
        attempts=MAX_ATTEMPTS,
    )
    stale = add_url(
        queue_db,
        canonical_url="https://example.com/stale.pdf",
        state="in_progress",
        attempts=MAX_ATTEMPTS,
        claimed_at=expired_claim_time(),
    )

    requests = run_start(ProcessUrlsSpider(limit=10))

    assert requests == []
    assert get_url(queue_db, errored).state == "error"
    assert get_url(queue_db, stale).state == "error"
    assert get_url(queue_db, stale).error_message == "Claim expired"
    assert get_url(queue_db, stale).attempts == MAX_ATTEMPTS


def test_request_failure_marks_url_error(queue_db):
    url_id = add_url(queue_db)
    [request] = run_start(ProcessUrlsSpider(limit=10))

    failure = Failure(DNSLookupError("no such host"))
    # Scrapy sets `request` on the Failure it passes to an errback; Twisted's
    # types do not declare it.
    # pyrefly: ignore[missing-attribute]
    failure.request = request
    request.errback(failure)

    row = get_url(queue_db, url_id)
    assert row.state == "error"
    assert row.error_message is not None and "no such host" in row.error_message
    assert row.completed_at is not None
