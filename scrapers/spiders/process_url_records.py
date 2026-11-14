from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta
from typing import Any, cast, override

import logfire
import scrapy
from ingest.pdf_text import extract_pdf_text
from ingest.pdf_urls import ErrorKind, mark_error, utc_now
from items import PoliceLogPdfItem
from models import PdfUrlClaim
from mongo.archive import content_hash
from postgres import SessionLocal
from postgres.models.pdf_url import PdfUrl
from scrapy.http import Request, Response
from sqlalchemy import CursorResult, Update, select, update
from twisted.python.failure import Failure

CLAIM_LEASE = timedelta(hours=2)
MAX_ATTEMPTS = 3


def expire_stale_claims(now: datetime) -> Update:
    # A crashed run leaves its claims in_progress. Expire them to a download error
    # so the attempt limit in retry_failed_urls applies to them too.
    return (
        update(PdfUrl)
        .where(PdfUrl.state == "in_progress", PdfUrl.claimed_at < now - CLAIM_LEASE)
        .values(
            state="error",
            error_kind="download",
            error_message="Claim expired",
            completed_at=now,
        )
    )


def retry_failed_urls() -> Update:
    # Only a download can go differently next time. A parse or save error has its
    # text stored and waits for a parser fix and a reprocess.
    return (
        update(PdfUrl)
        .where(
            PdfUrl.state == "error",
            PdfUrl.error_kind == "download",
            PdfUrl.attempts < MAX_ATTEMPTS,
        )
        .values(state="pending")
    )


def claim_statement(limit: int, now: datetime) -> Update:
    # SKIP LOCKED lets concurrent runs split the queue instead of waiting on each other.
    claimable = (
        select(PdfUrl.id)
        .where(PdfUrl.state == "pending")
        .order_by(PdfUrl.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return (
        update(PdfUrl)
        .where(PdfUrl.id.in_(claimable))
        .values(state="in_progress", claimed_at=now, attempts=PdfUrl.attempts + 1)
        .returning(PdfUrl.id, PdfUrl.canonical_url, PdfUrl.archive_url)
    )


class ProcessUrlsSpider(scrapy.Spider):
    name = "process_urls"
    archive_source = "police_log_pdf"
    # One at a time, so each PDF's callback knows whether its original was kept.
    archive_batch_size = 1

    def archive_key(self, response: Response) -> str | None:
        # The city sometimes answers 200 with an HTML page; that is not the original.
        if not response.body.startswith(b"%PDF"):
            return None
        # Keyed by the city URL, even when the PDF came from its Wayback copy.
        assert response.request is not None
        pdf_url: PdfUrlClaim = response.request.cb_kwargs["pdf_url"]
        return pdf_url.canonical_url

    # `scrapy crawl -a limit=10` passes the value as a string.
    def __init__(self, limit: int | str = 10, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.limit = int(limit)

    @override
    async def start(self) -> AsyncIterator[Request]:
        claimed = self._claim_urls()
        logfire.info("queued urls for processing", count=len(claimed), limit=self.limit)
        for pdf_url in claimed:
            yield Request(
                pdf_url.canonical_url,
                cb_kwargs={"pdf_url": pdf_url},
                errback=self._on_request_error,
                dont_filter=True,
            )

    def _claim_urls(self) -> list[PdfUrlClaim]:
        now = utc_now()
        with (
            logfire.span("claim pdf urls", limit=self.limit),
            SessionLocal() as session,
        ):
            # UPDATEs return a CursorResult; Session.execute is typed for SELECTs.
            expired = cast(
                CursorResult[Any], session.execute(expire_stale_claims(now))
            ).rowcount
            retried = cast(
                CursorResult[Any], session.execute(retry_failed_urls())
            ).rowcount
            rows = session.execute(claim_statement(self.limit, now)).all()
            session.commit()
            logfire.info("requeued failed urls", expired=expired, retried=retried)
        return [PdfUrlClaim.model_validate(row, from_attributes=True) for row in rows]

    def _on_request_error(self, failure: Failure) -> None:
        # Scrapy sets `request` on the Failure it passes to an errback; Twisted's
        # types do not declare it.
        # pyrefly: ignore[missing-attribute]
        request: Request = failure.request
        pdf_url = request.cb_kwargs["pdf_url"]
        logfire.error("request failed", url=request.url, error=repr(failure.value))
        self._mark_error(pdf_url, "download", f"Request failed: {failure.value!r}")

    # Scrapy types Spider.parse as a callback attribute, which any method override
    # trips; callbacks are meant to be overridden like this.
    @override
    # pyrefly: ignore[bad-override-mutable-attribute]
    def parse(
        self, response: Response, pdf_url: PdfUrlClaim, **kwargs: Any
    ) -> Iterator[Request | PoliceLogPdfItem]:
        if not response.body.startswith(b"%PDF"):
            if pdf_url.archive_url:
                logfire.warning(
                    "canonical url not a pdf, trying archive", url=response.url
                )
                yield Request(
                    pdf_url.archive_url,
                    callback=self.parse_archive,
                    cb_kwargs={"pdf_url": pdf_url},
                    errback=self._on_request_error,
                )
            else:
                logfire.error("response is not a pdf, no archive url", url=response.url)
                self._mark_error(
                    pdf_url,
                    "download",
                    "Response is not a PDF and no archive URL available",
                )
            return

        yield from self._process_pdf(response, response.url, pdf_url)

    def parse_archive(
        self, response: Response, pdf_url: PdfUrlClaim, **kwargs: Any
    ) -> Iterator[PoliceLogPdfItem]:
        if not response.body.startswith(b"%PDF"):
            logfire.error("archive url also not a pdf", url=response.url)
            self._mark_error(pdf_url, "download", "Archive URL also not a PDF")
            return
        yield from self._process_pdf(response, pdf_url.canonical_url, pdf_url)

    def _process_pdf(
        self, response: Response, source_url: str, pdf_url: PdfUrlClaim
    ) -> Iterator[PoliceLogPdfItem]:
        pdf_bytes = response.body
        try:
            with logfire.span("extract pdf text", url=source_url):
                raw_text = extract_pdf_text(pdf_bytes)
        except Exception as exc:
            logfire.error("pdf text extraction failed", url=source_url, error=repr(exc))
            # No text came out, so there is nothing for a parser fix to work on.
            # A truncated download lands here, and another download may succeed.
            self._mark_error(
                pdf_url, "download", f"PDF text extraction failed: {exc!r}"
            )
            return

        # One item per PDF. The pipeline parses the text, saves the entries, and
        # completes the URL in one commit.
        yield PoliceLogPdfItem(
            url_id=pdf_url.id,
            raw_text=raw_text,
            content_hash=content_hash("police_log_pdf", pdf_bytes),
            # Set by the raw archive middleware. Missing means the archive is off.
            original_archived=response.meta.get("archived", False),
        )

    def _mark_error(self, pdf_url: PdfUrlClaim, kind: ErrorKind, message: str) -> None:
        with SessionLocal() as session:
            session.execute(mark_error(pdf_url.id, kind, message))
            session.commit()
