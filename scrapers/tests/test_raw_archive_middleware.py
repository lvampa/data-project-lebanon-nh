import gzip
import socket
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from items import PoliceLogItem, PoliceLogPdfItem
from middlewares.raw_archive import RawArchiveMiddleware
from models import PdfUrlClaim
from mongo.archive import RawArchive, archive_collection
from mongo.client import MongoDB
from pipelines import PoliceLogPipeline
from postgres.models.log_entry import LogEntry
from postgres.models.pdf_url import PdfUrl
from scrapy.downloadermiddlewares.httpcompression import HttpCompressionMiddleware
from scrapy.exceptions import NotConfigured
from scrapy.http import HtmlResponse, Request, Response
from scrapy.settings import Settings
from scrapy.settings.default_settings import DOWNLOADER_MIDDLEWARES_BASE
from settings import DOWNLOADER_MIDDLEWARES
from spiders.city_staff import CityStaffSpider
from spiders.process_url_records import ProcessUrlsSpider
from spiders.vgsi_property import VgsiPropertySpider
from sqlalchemy import select

CITY_URL = "https://www.lebanonnh.gov/DocumentCenter/View/23007/2026-05-11"
WAYBACK_URL = f"https://web.archive.org/web/2026/{CITY_URL}"
PDF = b"%PDF-1.4 a police log"
PARCEL_URL = "https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=1000"
STREET_URL = "https://gis.vgsi.com/LebanonNH/Streets.aspx?Name=MAIN"


def fake_crawler(spider: object, **settings: object) -> SimpleNamespace:
    return SimpleNamespace(
        spider=spider,
        settings=Settings({"RAW_ARCHIVE_ENABLED": True, **settings}),
        signals=MagicMock(),
    )


def pdf_response(url: str = CITY_URL, body: bytes = PDF, **kwargs: object) -> Response:
    claim = PdfUrlClaim(id=7, canonical_url=CITY_URL, archive_url=WAYBACK_URL)
    request = Request(url, cb_kwargs={"pdf_url": claim})
    return Response(url=url, body=body, request=request, **kwargs)


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

    assert middleware.process_response(response.request, response) is response

    [version] = archived(middleware, raw_sources)
    assert (version["source"], version["source_key"]) == ("police_log_pdf", CITY_URL)
    assert version["content_type"] == "application/pdf"
    assert version["spider"] == "process_urls"
    assert gzip.decompress(version["body_gzip"]) == PDF


def test_a_pdf_fetched_from_its_wayback_copy_keeps_the_city_url_as_key(raw_sources):
    middleware = middleware_for(process_spider(), raw_sources)
    response = pdf_response(WAYBACK_URL)

    middleware.process_response(response.request, response)

    [version] = archived(middleware, raw_sources)
    assert version["source_key"] == CITY_URL
    assert version["url"] == WAYBACK_URL


def test_an_html_page_where_a_pdf_was_expected_is_not_archived(raw_sources):
    middleware = middleware_for(process_spider(), raw_sources)
    response = pdf_response(body=b"<html>not a pdf</html>")

    middleware.process_response(response.request, response)

    assert archived(middleware, raw_sources) == []


def test_a_parcel_page_is_archived_under_its_parcel_id(raw_sources):
    middleware = middleware_for(VgsiPropertySpider(), raw_sources)
    response = HtmlResponse(PARCEL_URL, body=b"<html>parcel</html>")

    middleware.process_response(Request(PARCEL_URL), response)

    [version] = archived(middleware, raw_sources)
    assert (version["source"], version["source_key"]) == ("vgsi_parcel", "1000")


def test_a_street_index_page_is_not_archived(raw_sources):
    middleware = middleware_for(VgsiPropertySpider(), raw_sources)
    response = HtmlResponse(STREET_URL, body=b"<html>street</html>")

    middleware.process_response(Request(STREET_URL), response)

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

    middleware.process_response(response.request, response)

    assert archived(middleware, raw_sources) == []


def test_a_spider_that_does_not_opt_in_is_not_archived(raw_sources):
    middleware = middleware_for(CityStaffSpider(), raw_sources)
    response = HtmlResponse("https://www.lebanonnh.gov/796", body=b"<html></html>")

    middleware.process_response(Request(response.url), response)

    assert archived(middleware, raw_sources) == []


def test_it_runs_after_decompression_and_redirects():
    # Scrapy calls process_response from the highest number to the lowest, so a
    # lower number sees the body the callback sees.
    ours = DOWNLOADER_MIDDLEWARES["middlewares.raw_archive.RawArchiveMiddleware"]
    base = DOWNLOADER_MIDDLEWARES_BASE
    assert (
        ours
        < base["scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware"]
    )
    assert ours < base["scrapy.downloadermiddlewares.redirect.RedirectMiddleware"]


def test_a_gzip_encoded_response_is_archived_decompressed(raw_sources):
    middleware = middleware_for(process_spider(), raw_sources)
    encoded = pdf_response(
        body=gzip.compress(PDF), headers={"Content-Encoding": "gzip"}
    )

    decoded = HttpCompressionMiddleware().process_response(encoded.request, encoded)
    middleware.process_response(encoded.request, decoded)

    [version] = archived(middleware, raw_sources)
    assert gzip.decompress(version["body_gzip"]) == PDF


def test_the_setting_turns_it_off():
    crawler = fake_crawler(process_spider(), RAW_ARCHIVE_ENABLED=False)

    with pytest.raises(NotConfigured):
        RawArchiveMiddleware.from_crawler(crawler)


def test_it_flushes_when_the_spider_closes():
    crawler = fake_crawler(process_spider())

    middleware = RawArchiveMiddleware.from_crawler(crawler)

    crawler.signals.connect.assert_called_once()
    assert crawler.signals.connect.call_args.args[0] == middleware.spider_closed


def closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_entries_are_stored_when_mongodb_is_unreachable(db_session, monkeypatch):
    monkeypatch.setenv("MONGO_HOST", "127.0.0.1")
    monkeypatch.setenv("MONGO_PORT", str(closed_port()))
    archive = RawArchive(archive_collection(MongoDB()))
    middleware = RawArchiveMiddleware(fake_crawler(process_spider()), archive)
    url = PdfUrl(
        canonical_url=CITY_URL, state="in_progress", created_at=datetime(2026, 5, 12)
    )
    db_session.add(url)
    db_session.commit()
    entry = PoliceLogItem(
        source_url=CITY_URL,
        raw_text="26-13339 0106 Phone - Noise Complaint",
        scraped_at=datetime.now(UTC),
        case_number="26-13339",
    )

    response = pdf_response()
    middleware.process_response(response.request, response)
    pipeline = PoliceLogPipeline()
    pipeline.open_spider(None)
    pipeline.process_item(
        PoliceLogPdfItem(url_id=url.id, raw_text="text", entries=[entry]), None
    )
    middleware.spider_closed()

    assert archive.is_down is True
    stored = db_session.scalars(select(LogEntry.case_number)).all()
    assert stored == ["26-13339"]
