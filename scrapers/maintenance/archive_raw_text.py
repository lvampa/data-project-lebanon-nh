"""Copy the raw text Postgres and the old Mongo urls collection hold into the archive.

Run this before the migration that drops pdf_urls.raw_text, log_entries.raw_text,
log_entries.raw_reason_action and log_entries.scraped_at. That migration refuses to
drop the text until every value is in the archive.

    uv run python -m maintenance.archive_raw_text

It copies:
- every pdf_urls.raw_text, as a police_log_text version keyed by canonical URL;
- every urls document's raw_text, the same way, leaving urls unchanged;
- every log_entries row's raw_text and raw_reason_action, as a police_log_entry_text
  version keyed by case number. Rows parsed before the parser had a version carry a
  null parser_version.

It only reads Postgres and urls. A second run stores and changes nothing.
"""

import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from mongo.archive import (
    ArchivedResponse,
    archive_collection,
    content_hash,
    version_insert,
)
from mongo.client import MongoDB
from mongo.raw_text import ENTRY_TEXT_SOURCE, PDF_TEXT_SOURCE, entry_text
from postgres import SessionLocal
from pymongo import UpdateOne
from pymongo.collection import Collection
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

# The last migration with the raw text columns still in place.
BEFORE_DROP = "3f1a9c7e2b54"
BATCH_SIZE = 500
SPIDER = "archive_raw_text"

# Plain SQL, because the ORM models no longer have these columns.
_PDF_TEXT = text(
    "SELECT canonical_url, raw_text FROM pdf_urls WHERE raw_text IS NOT NULL"
)
_ENTRY_TEXT = text(
    "SELECT case_number, raw_text, raw_reason_action, source_url, parser_version"
    " FROM log_entries WHERE raw_text IS NOT NULL"
)
# Where the process job kept PDF text before Postgres had a URL queue.
LEGACY_URLS = "urls"
_LEGACY_TEXT = {"raw_text": {"$type": "string", "$ne": ""}}


@dataclass(frozen=True)
class CopyResult:
    origin: str
    found: int
    archived: int

    @property
    def complete(self) -> bool:
        return self.archived == self.found


@dataclass(frozen=True)
class _Copy:
    """One text to archive, and the version it becomes."""

    source: str
    source_key: str
    response: ArchivedResponse

    @property
    def version(self) -> tuple[str, str]:
        return (self.source_key, content_hash(self.source, self.response.body))


def main() -> int:
    with SessionLocal() as session:
        if not _raw_text_columns_exist(session):
            print("Nothing to copy: the raw text columns are already dropped.")
            return 0
        results = copy_raw_text(session, archive_collection(MongoDB()))

    for result in results:
        print(f"{result.origin}: {result.found} found, {result.archived} archived")
    if all(result.complete for result in results):
        print("Every value is archived. The migration can drop the columns now.")
        return 0
    print("Some values are not archived. Do not drop the columns.", file=sys.stderr)
    return 1


def copy_raw_text(session: Session, collection: Collection) -> list[CopyResult]:
    """Archive every raw text value, then check each one arrived."""
    copied_at = datetime.now(UTC)
    origins = {
        "pdf_urls.raw_text": list(_pdf_texts(session, copied_at)),
        "urls.raw_text": list(
            _legacy_texts(collection.database[LEGACY_URLS], copied_at)
        ),
        "log_entries.raw_text": list(_entry_texts(session, copied_at)),
    }
    for copies in origins.values():
        _write(
            collection,
            (version_insert(c.source, c.source_key, c.response) for c in copies),
        )
    return [_check(origin, copies, collection) for origin, copies in origins.items()]


def _check(origin: str, copies: list[_Copy], collection: Collection) -> CopyResult:
    """Count the copies whose exact version is in the archive."""
    stored: set[tuple[str, str]] = set()
    for source in {copy.source for copy in copies}:
        stored |= {
            (doc["source_key"], doc["content_hash"])
            for doc in collection.find(
                {"source": source}, {"source_key": 1, "content_hash": 1}
            )
        }
    expected = {copy.version for copy in copies}
    return CopyResult(origin, found=len(expected), archived=len(expected & stored))


def _raw_text_columns_exist(session: Session) -> bool:
    pdf_url_columns = inspect(session.connection()).get_columns("pdf_urls")
    return any(column["name"] == "raw_text" for column in pdf_url_columns)


def _pdf_texts(session: Session, copied_at: datetime) -> Iterator[_Copy]:
    for row in session.execute(_PDF_TEXT):
        yield _pdf_text(row.canonical_url, row.raw_text, copied_at)


def _legacy_texts(urls: Collection, copied_at: datetime) -> Iterator[_Copy]:
    for doc in urls.find(_LEGACY_TEXT, {"canonical_url": 1, "raw_text": 1}):
        yield _pdf_text(doc["canonical_url"], doc["raw_text"], copied_at)


def _pdf_text(canonical_url: str, raw_text: str, copied_at: datetime) -> _Copy:
    return _Copy(
        PDF_TEXT_SOURCE,
        canonical_url,
        ArchivedResponse(
            url=canonical_url,
            status=200,
            content_type="text/plain; charset=utf-8",
            body=raw_text.encode(),
            fetched_at=copied_at,
            spider=SPIDER,
        ),
    )


def _entry_texts(session: Session, copied_at: datetime) -> Iterator[_Copy]:
    for row in session.execute(_ENTRY_TEXT):
        response = entry_text(
            source_url=row.source_url,
            raw_text=row.raw_text,
            raw_reason_action=row.raw_reason_action,
            parser_version=row.parser_version,
            fetched_at=copied_at,
            spider=SPIDER,
        )
        yield _Copy(ENTRY_TEXT_SOURCE, row.case_number, response)


def _write(collection: Collection, writes: Iterable[UpdateOne]) -> None:
    # Unlike the crawl's archive, a failure here has to stop the run, so errors are
    # not caught.
    batch: list[UpdateOne] = []
    for write in writes:
        batch.append(write)
        if len(batch) == BATCH_SIZE:
            collection.bulk_write(batch, ordered=False)
            batch = []
    if batch:
        collection.bulk_write(batch, ordered=False)


if __name__ == "__main__":
    sys.exit(main())
