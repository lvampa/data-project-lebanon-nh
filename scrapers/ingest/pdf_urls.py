"""Statements that move a PDF URL record to `error`, shared by the spider and pipeline."""

from typing import Literal

from postgres import utc_now
from postgres.models.pdf_url import PdfUrl
from sqlalchemy import Update, update

ErrorKind = Literal["download", "parse", "save"]


def mark_error(url_id: int, kind: ErrorKind, message: str) -> Update:
    return (
        update(PdfUrl)
        .where(PdfUrl.id == url_id)
        .values(
            state="error",
            error_kind=kind,
            error_message=message,
            completed_at=utc_now(),
        )
    )


def kept_for_reprocess(kind: ErrorKind, original_archived: bool) -> ErrorKind:
    """The kind for a parse or save error, given whether its original was archived.

    Those errors wait for a reprocess, which reads the archived original. Without
    one, the only way back to the PDF is downloading it again.
    """
    return kind if original_archived else "download"
