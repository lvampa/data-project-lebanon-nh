"""The only place that parses police log text and writes its entries.

The process job calls this for a fresh download and the reprocess job for stored
text, so both write entries the same way.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import logfire
import pypdf
from models.police_log import PoliceLogRecord
from parsers.police_log import (
    PARSER_VERSION,
    count_header_lines,
    parse_log_date,
    parse_log_entries,
)
from postgres.models.log_entry import LogEntry
from postgres.models.pdf_url import PdfUrl
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ingest.pdf_urls import kept_for_reprocess

# Bookkeeping about the write, not values read from the PDF. A change in these
# alone does not make an entry "updated".
_BOOKKEEPING_FIELDS = {"scraped_at", "parser_version"}


@dataclass(frozen=True)
class IngestCounts:
    parsed: int
    inserted: int
    updated: int
    unchanged: int
    skipped: int
    missing: int
    header_lines: int
    # The valid entries this parse cut, so the caller can archive their texts.
    records: tuple[PoliceLogRecord, ...] = field(default=(), compare=False)

    @property
    def stored(self) -> int:
        return self.inserted + self.updated + self.unchanged


def ingest_pdf_url(
    session: Session,
    pdf_url: PdfUrl,
    text: str,
    *,
    content_hash: str,
    original_archived: bool,
) -> IngestCounts:
    """Ingest one PDF's text and record the outcome on its URL record.

    `content_hash` names the PDF's original in the raw archive. `original_archived`
    says whether that original can be reprocessed, which decides how an error waits.
    The caller commits, so the entries and the URL's new state land together.
    """
    counts = ingest_log_text(session, pdf_url, text)
    _record_outcome(pdf_url, content_hash, counts, original_archived)
    return counts


def ingest_log_text(session: Session, pdf_url: PdfUrl, text: str) -> IngestCounts:
    """Parse one PDF's text and upsert its entries by case number."""
    now = _utc_now()
    log_date = pdf_url.log_date or parse_log_date(text)
    parsed_entries = parse_log_entries(text)

    records = _valid_records(parsed_entries, pdf_url, log_date, scraped_at=now)
    stored = _stored_entries(session, [record.case_number for record in records])

    inserted = updated = unchanged = 0
    for record in records:
        existing = stored.get(record.case_number)
        values = record.model_dump()
        if existing is None:
            _upsert_entry(session, values, now)
            inserted += 1
        elif _is_from_an_older_log(values, existing):
            # The same case number in two PDFs: the later log's row stays as it is.
            unchanged += 1
            continue
        elif _parsed_values_differ(values, existing):
            _upsert_entry(session, values, now)
            updated += 1
        else:
            _confirm_entry(session, record.case_number)
            unchanged += 1
        stored[record.case_number] = values

    missing = _flag_missing_entries(session, pdf_url.canonical_url, set(stored))

    counts = IngestCounts(
        parsed=len(parsed_entries),
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
        skipped=len(parsed_entries) - len(records),
        missing=missing,
        header_lines=count_header_lines(text),
        records=tuple(records),
    )
    _warn_on_unread_headers(pdf_url, counts)
    return counts


def _utc_now() -> datetime:
    # Timestamp columns are naive and hold UTC, like the other tables.
    return datetime.now(UTC).replace(tzinfo=None)


def _valid_records(
    parsed_entries: list[dict[str, Any]],
    pdf_url: PdfUrl,
    log_date: date | None,
    scraped_at: datetime,
) -> list[PoliceLogRecord]:
    records = []
    for entry in parsed_entries:
        try:
            record = PoliceLogRecord.model_validate(
                {
                    **entry,
                    "source_url": pdf_url.canonical_url,
                    "log_date": log_date,
                    "scraped_at": scraped_at,
                    "parser_version": PARSER_VERSION,
                }
            )
        except ValidationError as exc:
            logfire.warning(
                "skipped invalid police log entry",
                url=pdf_url.canonical_url,
                case_number=entry.get("case_number"),
                errors=exc.error_count(),
            )
            continue
        records.append(record)
    return records


def _stored_entries(session: Session, case_numbers: list[str]) -> dict[str, Any]:
    rows = session.scalars(
        select(LogEntry).where(LogEntry.case_number.in_(case_numbers))
    )
    return {row.case_number: row for row in rows}


def _is_from_an_older_log(values: dict[str, Any], existing: Any) -> bool:
    return values["log_date"] < _stored_value(existing, "log_date")


def _parsed_values_differ(values: dict[str, Any], existing: Any) -> bool:
    return any(
        values[field] != _stored_value(existing, field)
        for field in values.keys() - _BOOKKEEPING_FIELDS
    )


def _stored_value(existing: Any, field: str) -> Any:
    # A case number repeated inside one PDF is compared with the values just written.
    return existing[field] if isinstance(existing, dict) else getattr(existing, field)


def _upsert_entry(session: Session, values: dict[str, Any], now: datetime) -> None:
    insert = pg_insert(LogEntry).values(**values, created_at=now, updated_at=now)
    parsed_values = {
        field: insert.excluded[field] for field in values if field != "scraped_at"
    }
    session.execute(
        insert.on_conflict_do_update(
            index_elements=["case_number"],
            set_={**parsed_values, "missing_from_parse": False, "updated_at": now},
            # Repeats _is_from_an_older_log, for a row another run stored meanwhile.
            where=insert.excluded.log_date >= LogEntry.log_date,
        )
    )


def _confirm_entry(session: Session, case_number: str) -> None:
    """Note that this parser version still reads the entry, without touching updated_at."""
    session.execute(
        update(LogEntry)
        .where(
            LogEntry.case_number == case_number,
            LogEntry.parser_version.is_distinct_from(PARSER_VERSION)
            | LogEntry.missing_from_parse,
        )
        .values(parser_version=PARSER_VERSION, missing_from_parse=False)
    )


def _flag_missing_entries(
    session: Session, source_url: str, parsed_case_numbers: set[str]
) -> int:
    """Flag entries stored from this PDF that this parse no longer produces."""
    missing = session.scalars(
        select(LogEntry.case_number).where(
            LogEntry.source_url == source_url,
            LogEntry.case_number.not_in(parsed_case_numbers),
        )
    ).all()
    if missing:
        session.execute(
            update(LogEntry)
            .where(
                LogEntry.case_number.in_(missing),
                LogEntry.missing_from_parse.is_(False),
            )
            .values(missing_from_parse=True)
        )
    return len(missing)


def _warn_on_unread_headers(pdf_url: PdfUrl, counts: IngestCounts) -> None:
    if counts.header_lines != counts.parsed:
        logfire.warning(
            "police log header lines differ from parsed entries",
            url=pdf_url.canonical_url,
            header_lines=counts.header_lines,
            parsed=counts.parsed,
        )


def _record_outcome(
    pdf_url: PdfUrl,
    content_hash: str,
    counts: IngestCounts,
    original_archived: bool,
) -> None:
    pdf_url.content_hash = content_hash
    pdf_url.extractor_version = pypdf.__version__
    pdf_url.parsed_count = counts.parsed
    pdf_url.stored_count = counts.stored
    pdf_url.skipped_count = counts.skipped
    pdf_url.header_lines = counts.header_lines
    pdf_url.parser_version = PARSER_VERSION
    pdf_url.completed_at = _utc_now()
    if counts.stored:
        pdf_url.state = "complete"
        pdf_url.error_kind = None
        pdf_url.error_message = None
    else:
        # A parse error waits for a parser fix and a reprocess, which reads the
        # archived original; downloading again would give the same text.
        pdf_url.state = "error"
        pdf_url.error_kind = kept_for_reprocess("parse", original_archived)
        pdf_url.error_message = "No entries stored from PDF"
