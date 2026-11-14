"""Reparse stored police log PDFs from the raw archive. Nothing is downloaded.

Run from scrapers/, after a parser fix:

    uv run python -m maintenance.reprocess_police_logs --all
    uv run python -m maintenance.reprocess_police_logs --from 2026-05-01 --to 2026-05-31

It works through `complete` and `error` URL records in log date order. For each, it
takes the newest archived PDF, extracts its text, and ingests it the way the process
job does. A record with no archived original goes back to `pending`, so the process
job downloads and archives it again. Normalizations are never touched.

It takes the same lock as the process job, so the two never run together.
"""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date
from typing import Self

import logfire
from ingest import ingest_pdf_url
from ingest.lock import police_log_lock
from ingest.pdf_text import extract_pdf_text
from ingest.police_log import archive_entry_texts
from mongo.archive import RawArchive, RawCollection, archive_collection, stored_body
from mongo.client import MongoDB
from postgres import SessionLocal, engine
from postgres.models.pdf_url import PdfUrl
from pymongo.errors import PyMongoError
from sqlalchemy import select

PDF_SOURCE = "police_log_pdf"
SPIDER = "reprocess_police_logs"
REPROCESSED_STATES = ("complete", "error")


@dataclass(frozen=True)
class ReprocessCounts:
    urls: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    missing: int = 0
    requeued: int = 0
    failed: int = 0
    # 1 when the archive stopped answering and the run ended before the last record.
    stopped_early: int = 0

    def __add__(self, other: Self) -> Self:
        return type(self)(
            **{
                f.name: getattr(self, f.name) + getattr(other, f.name)
                for f in fields(self)
            }
        )


@dataclass(frozen=True)
class _Original:
    """What the archive holds for one URL: the PDF bytes and which version they are."""

    body: bytes
    content_hash: str

    def text(self) -> str:
        return extract_pdf_text(self.body)


def reprocess(
    archive: RawArchive, date_from: date | None, date_to: date | None
) -> ReprocessCounts:
    """Reprocess every matching URL record. With no dates, every record."""
    totals = ReprocessCounts()
    for url_id in _url_ids(date_from, date_to):
        try:
            totals += _reprocess_url(archive, url_id)
        except PyMongoError as exc:
            # An archive that cannot answer is not one with no original, so nothing is
            # requeued. Stop, and report what was done.
            logfire.error("archive stopped answering", error=repr(exc))
            totals += ReprocessCounts(urls=1, failed=1, stopped_early=1)
            break
    return totals


def _url_ids(date_from: date | None, date_to: date | None) -> list[int]:
    query = select(PdfUrl.id).where(PdfUrl.state.in_(REPROCESSED_STATES))
    if date_from is not None and date_to is not None:
        query = query.where(PdfUrl.log_date.between(date_from, date_to))
    with SessionLocal() as session:
        return list(
            session.scalars(
                query.order_by(PdfUrl.log_date.asc().nulls_last(), PdfUrl.id)
            )
        )


def _reprocess_url(archive: RawArchive, url_id: int) -> ReprocessCounts:
    # One transaction per record, so a failure loses only that record's work.
    with SessionLocal() as session:
        url = session.get(PdfUrl, url_id)
        if url is None:
            return ReprocessCounts(urls=1, failed=1)
        canonical_url = url.canonical_url

        original = _archived_original(archive, canonical_url)
        if original is None:
            url.state = "pending"
            url.error_kind = None
            url.error_message = None
            session.commit()
            logfire.warning("no archived original; requeued", url=canonical_url)
            return ReprocessCounts(urls=1, requeued=1)

        try:
            with logfire.span("reprocess police log pdf", url=canonical_url):
                ingested = ingest_pdf_url(
                    session,
                    url,
                    original.text(),
                    content_hash=original.content_hash,
                    original_archived=True,
                )
                session.commit()
        except Exception as exc:
            session.rollback()
            logfire.error("reprocess failed", url=canonical_url, error=repr(exc))
            return ReprocessCounts(urls=1, failed=1)

    archive_entry_texts(archive, ingested.entry_texts, SPIDER)
    return ReprocessCounts(
        urls=1,
        inserted=ingested.inserted,
        updated=ingested.updated,
        unchanged=ingested.unchanged,
        missing=ingested.missing,
    )


def _archived_original(archive: RawArchive, canonical_url: str) -> _Original | None:
    """The newest archived PDF, or None when there is none or it was too big to keep."""
    version = archive.newest(PDF_SOURCE, canonical_url)
    body = stored_body(version) if version is not None else None
    if version is None or body is None:
        return None
    return _Original(body, version["content_hash"])


def _archive_is_reachable(collection: RawCollection) -> bool:
    try:
        collection.database.client.admin.command("ping")
    except PyMongoError:
        return False
    return True


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--all", action="store_true", help="Every matching record.")
    parser.add_argument("--from", dest="date_from", type=date.fromisoformat)
    parser.add_argument("--to", dest="date_to", type=date.fromisoformat)
    args = parser.parse_args(argv)
    has_range = args.date_from is not None or args.date_to is not None
    if args.all == has_range:
        parser.error("give --all, or both --from and --to")
    if has_range and (args.date_from is None or args.date_to is None):
        parser.error("--from and --to go together")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    collection = archive_collection(MongoDB())
    # Checked before anything changes: with the archive down, every record would
    # look like it has no original and be sent back to be downloaded again.
    if not _archive_is_reachable(collection):
        print(
            "The raw archive is not reachable. Start MongoDB, then run this again.",
            file=sys.stderr,
        )
        return 1

    with police_log_lock(engine) as acquired:
        if not acquired:
            print(
                "Another police log job (process or reprocess) is running. "
                "Wait for it to finish, then run this again.",
                file=sys.stderr,
            )
            return 1
        result = reprocess(RawArchive(collection), args.date_from, args.date_to)

    logfire.info("police logs reprocessed", **result.__dict__)
    print(
        f"Reprocessed {result.urls} PDFs: {result.inserted} inserted, "
        f"{result.updated} updated, {result.unchanged} unchanged, "
        f"{result.missing} entries not found in the new parse. "
        f"{result.requeued} had no archived original and went back to pending, "
        f"{result.failed} failed."
        + (
            " The archive stopped answering, so the run stopped early."
            if result.stopped_early
            else ""
        )
    )
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
