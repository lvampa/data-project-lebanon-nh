import io
from datetime import UTC, datetime
from typing import Any

import logfire
import scrapy
from items import PoliceLogItem
from models import UrlDocument
from mongo import db
from parsers import parse_log_entries
from pypdf import PdfReader
from scrapy.http import Request, Response


class ProcessUrlsSpider(scrapy.Spider):
    name = "process_urls"

    def __init__(self, limit: int = 10, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.limit = int(limit)

    async def start(self):
        # Atomically claim URLs so concurrent runs don't double-process.
        # Crashed spiders leave URLs stuck in "in_progress"; reset them manually
        # or add a locked_at timeout if that becomes a problem.
        claimed = []
        for _ in range(self.limit):
            doc = db.get_collection("urls").find_one_and_update(
                {"state": "pending"},
                {"$set": {"state": "in_progress"}},
            )
            if doc is None:
                break
            claimed.append(doc)

        logfire.info("queued urls for processing", count=len(claimed), limit=self.limit)
        for doc in claimed:
            url_doc = UrlDocument(**doc)
            yield Request(url_doc.canonical_url, cb_kwargs={"url_doc": url_doc}, dont_filter=True)

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
        with logfire.span("extract pdf text", url=source_url):
            reader = PdfReader(io.BytesIO(pdf_bytes))
            raw_text = "\n".join(page.extract_text() for page in reader.pages)

        now = datetime.now(UTC)
        entries = parse_log_entries(raw_text)

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

        db.get_collection("urls").update_one(
            {"_id": url_doc.id},
            {
                "$set": {
                    "raw_text": raw_text,
                    "state": "complete",
                    "entry_count": len(entries),
                    "completed_at": now,
                }
            },
        )

        for entry in entries:
            yield PoliceLogItem(
                source_url=source_url,
                scraped_at=now,
                **entry,  # includes per-entry raw_text from the parser
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
