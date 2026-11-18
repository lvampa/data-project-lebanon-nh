import asyncio
import gzip
import socket
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from items import PoliceLogPdfItem
from middlewares.raw_archive import (
    RawArchiveMiddleware,
)
from models import PdfUrlClaim
from mongo.archive import RawArchive, RawCollection, archive_collection
from mongo.client import MongoDB
from pipelines import PoliceLogPipeline
from postgres.models.log_entry import LogEntry
from postgres.models.pdf_url import PdfUrl
from pymongo.errors import OperationFailure
from scrapy.crawler import Crawler
from scrapy.downloadermiddlewares.httpcompression import HttpCompressionMiddleware
from scrapy.exceptions import NotConfigured
from scrapy.http import HtmlResponse, Request, Response
from scrapy.settings import Settings
from scrapy.settings.default_settings import SPIDER_MIDDLEWARES_BASE
from scrapy.spiders import Spider
from settings import SPIDER_MIDDLEWARES
from spiders.process_url_records import ProcessUrlsSpider
from spiders.vgsi_property import VgsiPropertySpider
from sqlalchemy import select

SCRAPERS_DIR = Path(__file__).resolve().parents[1]
CITY_URL = "https://www.lebanonnh.gov/DocumentCenter/View/23007/2026-05-11"
WAYBACK_URL = f"https://web.archive.org/web/2026/{CITY_URL}"
PDF = b"%PDF-1.4 a police log"
PARCEL_URL = "https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=1000"
STREET_URL = "https://gis.vgsi.com/LebanonNH/Streets.aspx?Name=MAIN"


class FakeStats:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get_value(self, key: str) -> object:
        return self.values.get(key)

    def set_value(self, key: str, value: object) -> None:
        self.values[key] = value


def fake_crawler(spider: object, **settings: object) -> Crawler:
    stand_in = SimpleNamespace(
        spider=spider,
        spidercls=type(spider),
        settings=Settings({"RAW_ARCHIVE_ENABLED": True, **settings}),
        signals=MagicMock(),
        stats=FakeStats(),
    )
    return cast(Crawler, stand_in)


def pdf_response(url: str = CITY_URL, body: bytes = PDF, **kwargs: Any) -> Response:
    claim = PdfUrlClaim(id=7, canonical_url=CITY_URL, archive_url=WAYBACK_URL)
    request = Request(url, cb_kwargs={"pdf_url": claim})
    return Response(url=url, body=body, request=request, **kwargs)


def request_of(response: Response) -> Request:
    assert response.request is not None
    return response.request


def middleware_for(spider: object, raw_sources) -> RawArchiveMiddleware:
    return RawArchiveMiddleware(fake_crawler(spider), RawArchive(raw_sources))


def archived(middleware: RawArchiveMiddleware, raw_sources) -> list[dict]:
    middleware.spider_closed()
    return list(raw_sources.find())


def process_spider() -> ProcessUrlsSpider:
    return ProcessUrlsSpider.__new__(ProcessUrlsSpider)


def test_a_police_log_pdf_is_archived_under_its_city_url(raw_sources):
    middleware = middleware_for(process_spider(), raw_sources)
    response = pdf_response(headers={"Content-Type": "application/pdf"})

    middleware.process_spider_input(response)

    [version] = archived(middleware, raw_sources)
    assert (version["source"], version["source_key"]) == ("police_log_pdf", CITY_URL)
    assert version["content_type"] == "application/pdf"
    assert version["spider"] == "process_urls"
    assert gzip.decompress(version["body_gzip"]) == PDF


def test_a_pdf_fetched_from_its_wayback_copy_keeps_the_city_url_as_key(raw_sources):
    middleware = middleware_for(process_spider(), raw_sources)
    response = pdf_response(WAYBACK_URL)

    middleware.process_spider_input(response)

    [version] = archived(middleware, raw_sources)
    assert version["source_key"] == CITY_URL
    assert version["url"] == WAYBACK_URL


def test_an_html_page_where_a_pdf_was_expected_is_not_archived(raw_sources):
    middleware = middleware_for(process_spider(), raw_sources)
    response = pdf_response(body=b"<html>not a pdf</html>")

    middleware.process_spider_input(response)

    assert archived(middleware, raw_sources) == []


def test_a_parcel_page_is_archived_under_its_parcel_id(raw_sources):
    middleware = middleware_for(VgsiPropertySpider(), raw_sources)
    response = HtmlResponse(PARCEL_URL, body=b"<html>parcel</html>")

    middleware.process_spider_input(response)

    [version] = archived(middleware, raw_sources)
    assert (version["source"], version["source_key"]) == ("vgsi_parcel", "1000")


def test_a_street_index_page_is_not_archived(raw_sources):
    middleware = middleware_for(VgsiPropertySpider(), raw_sources)
    response = HtmlResponse(STREET_URL, body=b"<html>street</html>")

    middleware.process_spider_input(response)

    assert archived(middleware, raw_sources) == []


@pytest.mark.parametrize(
    "response",
    [
        pdf_response(status=404),
        pdf_response(flags=["cached"]),
    ],
    ids=["not_200", "from_the_http_cache"],
)
def test_only_fresh_200_responses_are_archived(raw_sources, response):
    middleware = middleware_for(process_spider(), raw_sources)

    middleware.process_spider_input(response)

    assert archived(middleware, raw_sources) == []


def test_a_spider_that_does_not_opt_in_is_not_archived(raw_sources):
    middleware = middleware_for(Spider(name="plain"), raw_sources)
    response = HtmlResponse("https://www.lebanonnh.gov/796", body=b"<html></html>")

    middleware.process_spider_input(response)

    assert archived(middleware, raw_sources) == []


def test_it_runs_after_the_http_error_middleware():
    # Lower numbers run first on the way in, and HttpErrorMiddleware is what stops
    # a non-2xx response before the callback.
    ours = SPIDER_MIDDLEWARES["middlewares.raw_archive.RawArchiveMiddleware"]
    http_error = SPIDER_MIDDLEWARES_BASE[
        "scrapy.spidermiddlewares.httperror.HttpErrorMiddleware"
    ]
    assert ours > http_error


def test_a_gzip_encoded_response_is_archived_decompressed(raw_sources):
    middleware = middleware_for(process_spider(), raw_sources)
    encoded = pdf_response(
        body=gzip.compress(PDF), headers={"Content-Encoding": "gzip"}
    )

    # Scrapy 2.20 made this middleware's process_response a coroutine.
    decoded = asyncio.run(
        HttpCompressionMiddleware().process_response(request_of(encoded), encoded)
    )
    assert isinstance(decoded, Response)
    middleware.process_spider_input(decoded)

    [version] = archived(middleware, raw_sources)
    assert gzip.decompress(version["body_gzip"]) == PDF


def test_the_setting_turns_it_off():
    crawler = fake_crawler(process_spider(), RAW_ARCHIVE_ENABLED=False)

    with pytest.raises(NotConfigured):
        RawArchiveMiddleware.from_crawler(crawler)


def test_it_flushes_when_the_spider_closes():
    crawler = fake_crawler(process_spider())

    middleware = RawArchiveMiddleware.from_crawler(crawler)

    connect = cast(MagicMock, crawler.signals).connect
    connect.assert_called_once()
    assert connect.call_args.args[0] == middleware.spider_closed


def test_each_police_pdf_is_written_before_its_callback_and_flagged(raw_sources):
    middleware = RawArchiveMiddleware.from_crawler(fake_crawler(process_spider()))
    response = pdf_response()

    middleware.process_spider_input(response)

    # Not flushed: the write already happened in process_spider_input.
    assert raw_sources.count_documents({"source": "police_log_pdf"}) == 1
    assert response.meta["archived"] is True


CRAWL_SCRIPT = """
import scrapy
from scrapy.crawler import CrawlerProcess

from settings import SPIDER_MIDDLEWARES


class ProbeSpider(scrapy.Spider):
    name = "archive_probe"
    archive_source = "probe_pdf"
    archive_batch_size = 1
    start_urls = ["data:application/pdf,%25PDF-1.4%20probe"]

    def archive_key(self, response):
        return "probe-key" if response.body.startswith(b"%PDF") else None

    def parse(self, response):
        print("ARCHIVED", response.meta.get("archived"), flush=True)


process = CrawlerProcess(
    {
        "SPIDER_MIDDLEWARES": SPIDER_MIDDLEWARES,
        "RAW_ARCHIVE_ENABLED": True,
        "TELNETCONSOLE_ENABLED": False,
        "LOG_LEVEL": "ERROR",
    }
)
process.crawl(ProbeSpider)
process.start()
"""


def test_a_real_crawl_archives_the_original_before_the_callback(raw_sources):
    # Unit tests with hand-built responses hid a bug where the middleware saw a
    # response that Scrapy had not yet attached its request to. A subprocess,
    # because a Twisted reactor cannot be restarted inside the test run.
    result = subprocess.run(
        [sys.executable, "-c", CRAWL_SCRIPT],
        cwd=SCRAPERS_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ARCHIVED True" in result.stdout
    stored = raw_sources.find_one({"source": "probe_pdf"})
    assert stored is not None
    assert stored["source_key"] == "probe-key"


def test_a_police_pdf_the_archive_could_not_write_is_flagged(monkeypatch):
    monkeypatch.setenv("MONGO_HOST", "127.0.0.1")
    monkeypatch.setenv("MONGO_PORT", str(closed_port()))
    middleware = RawArchiveMiddleware.from_crawler(fake_crawler(process_spider()))
    response = pdf_response()

    middleware.process_spider_input(response)

    assert response.meta["archived"] is False


def test_a_pdf_that_is_not_an_original_is_not_flagged(raw_sources):
    middleware = RawArchiveMiddleware.from_crawler(fake_crawler(process_spider()))
    response = pdf_response(body=b"<html>not a pdf</html>")

    middleware.process_spider_input(response)

    assert "archived" not in response.meta


def test_parcel_pages_are_batched_and_not_flagged(raw_sources):
    middleware = RawArchiveMiddleware.from_crawler(fake_crawler(VgsiPropertySpider()))
    response = HtmlResponse(
        PARCEL_URL, body=b"<html>parcel</html>", request=Request(PARCEL_URL)
    )

    middleware.process_spider_input(response)

    assert raw_sources.count_documents({}) == 0
    assert "archived" not in response.meta
    middleware.spider_closed()
    assert raw_sources.count_documents({"source": "vgsi_parcel"}) == 1


def closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def add_claimed_url(db_session) -> PdfUrlClaim:
    url = PdfUrl(
        canonical_url=CITY_URL,
        log_date=date(2026, 5, 11),
        state="in_progress",
        created_at=datetime(2026, 5, 12),
    )
    db_session.add(url)
    db_session.commit()
    return PdfUrlClaim(id=url.id, canonical_url=CITY_URL, archive_url=WAYBACK_URL)


def crawl_one_pdf(middleware: RawArchiveMiddleware, claim: PdfUrlClaim, text: str):
    """Download, callback and pipeline for one PDF, as the process job runs them."""
    request = Request(CITY_URL, cb_kwargs={"pdf_url": claim})
    response = Response(url=CITY_URL, body=PDF, request=request)
    middleware.process_spider_input(response)
    with patch("ingest.pdf_text.PdfReader") as pdf_reader:
        page = MagicMock()
        page.extract_text.return_value = text
        pdf_reader.return_value.pages = [page]
        [item] = list(process_spider().parse(response, pdf_url=claim))
    assert isinstance(item, PoliceLogPdfItem)
    pipeline = PoliceLogPipeline()
    pipeline.open_spider()
    try:
        pipeline.process_item(item)
    finally:
        pipeline.close_spider()


LOG_TEXT = (
    "For Date: 05/11/2026  -  Monday\n"
    "26-13339        0106 Phone - Noise Complaint Log Information\n"
    "  Location/Address:    MAIN ST\n"
)


def test_entries_are_stored_when_mongodb_is_unreachable(db_session, monkeypatch):
    monkeypatch.setenv("MONGO_HOST", "127.0.0.1")
    monkeypatch.setenv("MONGO_PORT", str(closed_port()))
    archive = RawArchive(archive_collection(MongoDB()), batch_size=1)
    middleware = RawArchiveMiddleware(fake_crawler(process_spider()), archive)

    crawl_one_pdf(middleware, add_claimed_url(db_session), LOG_TEXT)
    middleware.spider_closed()

    assert archive.is_down is True
    stored = db_session.scalars(select(LogEntry.case_number)).all()
    assert stored == ["26-13339"]


class FailingCollection:
    """A collection whose writes fail without a timeout, as on a full disk."""

    def bulk_write(self, operations, ordered: bool):
        raise OperationFailure("disk full")


def test_a_pdf_whose_write_failed_is_downloaded_again_after_a_parse_error(
    db_session,
):
    archive = RawArchive(cast(RawCollection, FailingCollection()), batch_size=1)
    middleware = RawArchiveMiddleware(fake_crawler(process_spider()), archive)
    claim = add_claimed_url(db_session)

    crawl_one_pdf(middleware, claim, "not a police log")

    # The write failed but the archive is not down, so only the flag can tell.
    assert archive.is_down is False
    db_session.expire_all()
    url = db_session.get(PdfUrl, claim.id)
    assert (url.state, url.error_kind) == ("error", "download")
