"""Copy the raw text Postgres still holds into the raw archive, then check it.

Run this before the migration that drops pdf_urls.raw_text, log_entries.raw_text,
log_entries.raw_reason_action and log_entries.scraped_at. That migration refuses to
drop the text until every value is in the archive.

    uv run python -m maintenance.archive_raw_text

It only reads Postgres. Running it twice stores nothing new.
"""

import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from mongo.archive import ArchivedResponse, archive_collection, version_upsert
from mongo.client import MongoDB
from mongo.raw_text import ENTRY_TEXT_SOURCE, PDF_TEXT_SOURCE, archived_keys
from postgres import SessionLocal
from pymongo.collection import Collection
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

# The last migration with the raw text columns still in place.
BEFORE_DROP = "3f1a9c7e2b54"
BATCH_SIZE = 500

# Plain SQL, because the ORM models no longer have these columns.
_PDF_TEXT = text(
    "SELECT canonical_url, raw_text FROM pdf_urls WHERE raw_text IS NOT NULL"
)
_ENTRY_TEXT = text(
    "SELECT case_number, raw_text, raw_reason_action, source_url"
    " FROM log_entries WHERE raw_text IS NOT NULL"
)


@dataclass(frozen=True)
class CopyResult:
    source: str
    in_postgres: int
    in_archive: int

    @property
    def complete(self) -> bool:
        return self.in_archive == self.in_postgres


def main() -> int:
    with SessionLocal() as session:
        if not _raw_text_columns_exist(session):
            print("Nothing to copy: the raw text columns are already dropped.")
            return 0
        results = copy_raw_text(session, archive_collection(MongoDB()))

    for result in results:
        print(
            f"{result.source}: {result.in_postgres} in Postgres, "
            f"{result.in_archive} in the archive"
        )
    if all(result.complete for result in results):
        print("Every value is archived. The migration can drop the columns now.")
        return 0
    print("Some values are not archived. Do not drop the columns.", file=sys.stderr)
    return 1


def copy_raw_text(session: Session, collection: Collection) -> list[CopyResult]:
    """Archive every raw text value, then check each one arrived."""
    copied_at = datetime.now(UTC)
    _write(collection, _pdf_text_versions(session, copied_at))
    _write(collection, _entry_text_versions(session, copied_at))
    return check_raw_text_archived(session, collection)


def check_raw_text_archived(
    session: Session, collection: Collection
) -> list[CopyResult]:
    pdf_keys = {row.canonical_url for row in session.execute(_PDF_TEXT)}
    entry_keys = {row.case_number for row in session.execute(_ENTRY_TEXT)}
    return [
        _compare(PDF_TEXT_SOURCE, pdf_keys, collection),
        _compare(ENTRY_TEXT_SOURCE, entry_keys, collection),
    ]


def _compare(source: str, keys: set[str], collection: Collection) -> CopyResult:
    archived = archived_keys(collection, source) & keys
    return CopyResult(source, in_postgres=len(keys), in_archive=len(archived))


def _raw_text_columns_exist(session: Session) -> bool:
    pdf_url_columns = inspect(session.connection()).get_columns("pdf_urls")
    return any(column["name"] == "raw_text" for column in pdf_url_columns)


def _pdf_text_versions(session: Session, copied_at: datetime) -> Iterable:
    for row in session.execute(_PDF_TEXT):
        yield version_upsert(
            PDF_TEXT_SOURCE,
            row.canonical_url,
            _copied(
                row.canonical_url,
                "text/plain; charset=utf-8",
                row.raw_text.encode(),
                copied_at,
            ),
        )


def _entry_text_versions(session: Session, copied_at: datetime) -> Iterable:
    for row in session.execute(_ENTRY_TEXT):
        body = json.dumps(
            {
                "raw_text": row.raw_text,
                "raw_reason_action": row.raw_reason_action,
                "source_url": row.source_url,
            }
        ).encode()
        yield version_upsert(
            ENTRY_TEXT_SOURCE,
            row.case_number,
            _copied(row.source_url, "application/json", body, copied_at),
        )


def _copied(
    url: str, content_type: str, body: bytes, copied_at: datetime
) -> ArchivedResponse:
    return ArchivedResponse(
        url=url,
        status=200,
        content_type=content_type,
        body=body,
        fetched_at=copied_at,
        spider="archive_raw_text",
    )


def _write(collection: Collection, versions: Iterable) -> None:
    # Unlike the crawl's archive, a failure here has to stop the run, so errors are
    # not caught.
    batch = []
    for version in versions:
        batch.append(version)
        if len(batch) == BATCH_SIZE:
            collection.bulk_write(batch, ordered=False)
            batch = []
    if batch:
        collection.bulk_write(batch, ordered=False)


if __name__ == "__main__":
    sys.exit(main())
