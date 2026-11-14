"""Copies each original a spider downloads into the raw source archive.

It sits in the downloader middleware chain, so it sees the body before any callback
and the Postgres path never carries bodies around.

A spider opts in with two attributes:

    archive_source = "police_log_pdf"

    def archive_key(self, response: Response) -> str | None:
        # The source key, or None for a response that is not an original.

A spider may also set `archive_batch_size`, which defaults to 50. At 1, each original
is written before its callback runs, and `response.meta["archived"]` says whether
the write worked.
"""

from datetime import UTC, datetime
from typing import Protocol, Self, cast

import logfire
from mongo.archive import BATCH_SIZE, ArchivedResponse, RawArchive, archive_collection
from mongo.client import MongoDB
from scrapy import Spider, signals
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured
from scrapy.http import Request, Response


class ArchivedSpider(Protocol):
    name: str
    archive_source: str

    def archive_key(self, response: Response) -> str | None: ...


class RawArchiveMiddleware:
    def __init__(self, crawler: Crawler, archive: RawArchive) -> None:
        self._crawler = crawler
        self._archive = archive

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        if not crawler.settings.getbool("RAW_ARCHIVE_ENABLED"):
            raise NotConfigured("RAW_ARCHIVE_ENABLED is off")
        batch_size = getattr(crawler.spidercls, "archive_batch_size", BATCH_SIZE)
        archive = RawArchive(archive_collection(MongoDB()), batch_size=batch_size)
        middleware = cls(crawler, archive)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def process_response(self, request: Request, response: Response) -> Response:
        spider = self._crawler.spider
        if spider is None or not _is_archived(spider, response):
            return response
        archived_spider = cast(ArchivedSpider, spider)
        source_key = archived_spider.archive_key(response)
        if source_key is not None:
            written = self._archive.add(
                archived_spider.archive_source,
                source_key,
                _archived(archived_spider, response),
            )
            if written is not None:
                response.meta["archived"] = written
        return response

    def spider_closed(self) -> None:
        counts = self._archive.flush()
        logfire.info(
            "raw archive flushed",
            stored=counts.stored,
            seen_again=counts.seen_again,
            failed=counts.failed,
        )


def _is_archived(spider: Spider | None, response: Response) -> bool:
    return (
        getattr(spider, "archive_source", None) is not None
        # A cached response was archived when it was first downloaded.
        and "cached" not in response.flags
        and response.status == 200
    )


def _archived(spider: ArchivedSpider, response: Response) -> ArchivedResponse:
    content_type = response.headers.get("Content-Type")
    return ArchivedResponse(
        url=response.url,
        status=response.status,
        content_type=content_type.decode() if content_type else None,
        body=response.body,
        fetched_at=datetime.now(UTC),
        spider=spider.name,
    )
