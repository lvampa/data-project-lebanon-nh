import io
from datetime import UTC, datetime, timedelta
from typing import Any

import logfire
import scrapy
from items import PoliceLogItem, PoliceLogPdfItem
from models import PdfUrlClaim
from parsers import parse_log_entries
from postgres import SessionLocal
from postgres.models.pdf_url import PdfUrl
from pypdf import PdfReader
from scrapy.http import Request, Response
from sqlalchemy import Update, select, update
from twisted.python.failure import Failure

CLAIM_LEASE = timedelta(hours=2)
MAX_ATTEMPTS = 3


def expire_stale_claims(now: datetime) -> Update:
    # A crashed run leaves its claims in_progress. Expire them to error so the
    # attempt limit in retry_failed_urls applies to them too.
    return (
        update(PdfUrl)
        .where(PdfUrl.state == "in_progress", PdfUrl.claimed_at < now - CLAIM_LEASE)
        .values(state="error", error_message="Claim expired")
    )


def retry_failed_urls() -> Update:
    return (
        update(PdfUrl)
        .where(PdfUrl.state == "error", PdfUrl.attempts < MAX_ATTEMPTS)
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


def _utc_now() -> datetime:
    # pdf_urls timestamps are naive columns that hold UTC, like the other tables.
    return datetime.now(UTC).replace(tzinfo=None)


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
        pdf_url: PdfUrlClaim = response.request.cb_kwargs["pdf_url"]
        return pdf_url.canonical_url

    def __init__(self, limit: int = 10, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.limit = int(limit)

    async def start(self):
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
        now = _utc_now()
        with (
            logfire.span("claim pdf urls", limit=self.limit),
            SessionLocal() as session,
        ):
            expired = session.execute(expire_stale_claims(now)).rowcount
            retried = session.execute(retry_failed_urls()).rowcount
            rows = session.execute(claim_statement(self.limit, now)).all()
            session.commit()
            logfire.info("requeued failed urls", expired=expired, retried=retried)
        return [PdfUrlClaim.model_validate(row, from_attributes=True) for row in rows]

    def _on_request_error(self, failure: Failure) -> None:
        pdf_url = failure.request.cb_kwargs["pdf_url"]
        logfire.error(
            "request failed", url=failure.request.url, error=repr(failure.value)
        )
        self._mark_error(pdf_url, f"Request failed: {failure.value!r}")

    def parse(self, response: Response, pdf_url: PdfUrlClaim, **kwargs: Any) -> Any:
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
                    pdf_url, "Response is not a PDF and no archive URL available"
                )
            return

        yield from self._process_pdf(response.body, response.url, pdf_url)

    def parse_archive(
        self, response: Response, pdf_url: PdfUrlClaim, **kwargs: Any
    ) -> Any:
        if not response.body.startswith(b"%PDF"):
            logfire.error("archive url also not a pdf", url=response.url)
            self._mark_error(pdf_url, "Archive URL also not a PDF")
            return
        yield from self._process_pdf(response.body, pdf_url.canonical_url, pdf_url)

    def _process_pdf(
        self, pdf_bytes: bytes, source_url: str, pdf_url: PdfUrlClaim
    ) -> Any:
        try:
            with logfire.span("extract pdf text", url=source_url):
                reader = PdfReader(io.BytesIO(pdf_bytes))
                raw_text = "\n".join(page.extract_text() for page in reader.pages)
            entries = parse_log_entries(raw_text)
        except Exception as exc:
            logfire.error("pdf processing failed", url=source_url, error=repr(exc))
            self._mark_error(pdf_url, f"PDF processing failed: {exc!r}")
            return

        now = _utc_now()

        if not entries:
            logfire.warning("no entries parsed from pdf", url=source_url)
            self._update_url(
                pdf_url,
                raw_text=raw_text,
                state="error",
                error_message="No entries parsed from PDF",
                entry_count=0,
                completed_at=now,
            )
            return

        # One item per PDF so the pipeline saves its entries and completes the URL in one commit.
        yield PoliceLogPdfItem(
            url_id=pdf_url.id,
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

    def _mark_error(self, pdf_url: PdfUrlClaim, error_message: str) -> None:
        self._update_url(
            pdf_url, state="error", error_message=error_message, completed_at=_utc_now()
        )

    def _update_url(self, pdf_url: PdfUrlClaim, **values: Any) -> None:
        with SessionLocal() as session:
            session.execute(
                update(PdfUrl).where(PdfUrl.id == pdf_url.id).values(**values)
            )
            session.commit()
