"""Statements that move a PDF URL record to `error`, shared by the spider and pipeline."""

from datetime import UTC, datetime
from typing import Literal

from postgres.models.pdf_url import PdfUrl
from sqlalchemy import Update, update

ErrorKind = Literal["download", "parse", "save"]


def utc_now() -> datetime:
    # pdf_urls timestamps are naive columns that hold UTC, like the other tables.
    return datetime.now(UTC).replace(tzinfo=None)


def mark_error(
    url_id: int, kind: ErrorKind, message: str, raw_text: str | None = None
) -> Update:
    """Pass `raw_text` when the PDF's text was extracted, so a reprocess can use it."""
    values = {
        "state": "error",
        "error_kind": kind,
        "error_message": message,
        "completed_at": utc_now(),
    }
    if raw_text is not None:
        values["raw_text"] = raw_text
    return update(PdfUrl).where(PdfUrl.id == url_id).values(**values)
