import io
from datetime import UTC, datetime, timedelta
from typing import Any

import logfire
import scrapy
from items import PoliceLogItem, PoliceLogPdfItem
from models import UrlDocument
from mongo import db
from parsers import parse_log_entries
from pymongo.collection import Collection
from pypdf import PdfReader
from scrapy.http import Request, Response
from twisted.python.failure import Failure

CLAIM_LEASE = timedelta(hours=2)
MAX_ATTEMPTS = 3


class ProcessUrlsSpider(scrapy.Spider):
    name = "process_urls"

    def __init__(self, limit: int = 10, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.limit = int(limit)

    async def start(self):
        urls = db.get_collection("urls")
        self._requeue_failed_urls(urls)

        # Atomically claim URLs so concurrent runs don't double-process.
        claimed = []
        for _ in range(self.limit):
            doc = urls.find_one_and_update(
                {"state": "pending"},
                {
                    "$set": {"state": "in_progress", "claimed_at": datetime.now(UTC)},
                    "$inc": {"attempts": 1},
                },
            )
            if doc is None:
                break
            claimed.append(doc)

        logfire.info("queued urls for processing", count=len(claimed), limit=self.limit)
        for doc in claimed:
            url_doc = UrlDocument(**doc)
            yield Request(
                url_doc.canonical_url,
                cb_kwargs={"url_doc": url_doc},
                errback=self._on_request_error,
                dont_filter=True,
            )

    def _requeue_failed_urls(self, urls: Collection) -> None:
        # A crashed run leaves its claims in_progress. Expire them to error so
        # the attempt limit below applies to them too. $not also matches rows
        # claimed before claimed_at and attempts were recorded.
        lease_cutoff = datetime.now(UTC) - CLAIM_LEASE
        expired = urls.update_many(
            {"state": "in_progress", "claimed_at": {"$not": {"$gte": lease_cutoff}}},
            {"$set": {"state": "error", "error_message": "Claim expired"}},
        )
        retried = urls.update_many(
            {"state": "error", "attempts": {"$not": {"$gte": MAX_ATTEMPTS}}},
            {"$set": {"state": "pending"}},
        )
        logfire.info(
            "requeued failed urls",
            expired=expired.modified_count,
            retried=retried.modified_count,
        )

    def _on_request_error(self, failure: Failure) -> None:
        url_doc = failure.request.cb_kwargs["url_doc"]
        logfire.error(
            "request failed", url=failure.request.url, error=repr(failure.value)
        )
        self._mark_error(url_doc, f"Request failed: {failure.value!r}")

    def parse(self, response: Response, url_doc: UrlDocument, **kwargs: Any) -> Any:
        if not response.body.startswith(b"%PDF"):
            if url_doc.archive_url:
                logfire.warning(
                    "canonical url not a pdf, trying archive", url=response.url
                )
                yield Request(
                    url_doc.archive_url,
                    callback=self.parse_archive,
                    cb_kwargs={"url_doc": url_doc},
                    errback=self._on_request_error,
                )
            else:
                logfire.error("response is not a pdf, no archive url", url=response.url)
                self._mark_error(
                    url_doc, "Response is not a PDF and no archive URL available"
                )
            return

        yield from self._process_pdf(response.body, response.url, url_doc)

    def parse_archive(
        self, response: Response, url_doc: UrlDocument, **kwargs: Any
    ) -> Any:
        if not response.body.startswith(b"%PDF"):
            logfire.error("archive url also not a pdf", url=response.url)
            self._mark_error(url_doc, "Archive URL also not a PDF")
            return
        yield from self._process_pdf(response.body, url_doc.canonical_url, url_doc)

    def _process_pdf(
        self, pdf_bytes: bytes, source_url: str, url_doc: UrlDocument
    ) -> Any:
        try:
            with logfire.span("extract pdf text", url=source_url):
                reader = PdfReader(io.BytesIO(pdf_bytes))
                raw_text = "\n".join(page.extract_text() for page in reader.pages)
            entries = parse_log_entries(raw_text)
        except Exception as exc:
            logfire.error("pdf processing failed", url=source_url, error=repr(exc))
            self._mark_error(url_doc, f"PDF processing failed: {exc!r}")
            return

        # log_entries.scraped_at is a naive column that holds UTC, like the other writers.
        now = datetime.now(UTC).replace(tzinfo=None)

        if not entries:
            logfire.warning("no entries parsed from pdf", url=source_url)
            db.get_collection("urls").update_one(
                {"_id": url_doc.id},
                {
                    "$set": {
                        "raw_text": raw_text,
                        "state": "error",
                        "error_message": "No entries parsed from PDF",
                        "entry_count": 0,
                        "completed_at": now,
                    }
                },
            )
            return

        # One item per PDF so the pipeline saves all entries before it marks the URL complete.
        yield PoliceLogPdfItem(
            url_id=url_doc.id,
            raw_text=raw_text,
            entries=[
                PoliceLogItem(
                    source_url=source_url,
                    scraped_at=now,
                    **entry,  # includes per-entry raw_text from the parser
                )
                for entry in entries
            ],
        )

    def _mark_error(self, url_doc: UrlDocument, error_message: str) -> None:
        db.get_collection("urls").update_one(
            {"_id": url_doc.id},
            {
                "$set": {
                    "state": "error",
                    "error_message": error_message,
                    "completed_at": datetime.now(UTC),
                }
            },
        )
