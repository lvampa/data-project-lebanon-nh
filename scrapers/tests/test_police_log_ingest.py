from datetime import date, datetime

import pytest
from ingest.police_log import IngestCounts, ingest_log_text, ingest_pdf_url
from parsers.police_log import PARSER_VERSION
from postgres.models.log_entry import LogEntry
from postgres.models.pdf_url import PdfUrl
from sqlalchemy import select

HEADER = """\
 Lebanon Police Department Page:   1
  Dispatch Log  From: {date}  Thru: {date}     0000 - 2359    Printed: 05/14/2026
For Date: {date}  -  Monday
Call   Number   Time   Call   Reason   Action
"""

HARASSMENT = """\
26-13339        0106 Phone - Telephone Harassment Incident Report Taken
       Call Source:    Telephone
        Primary Id:    SMN - Officer Stephan Nix
  Location/Address:    TIMBERWOOD DR
"""

PATROL = """\
26-13340        0212 Initiated - Directed Patrol Log Information
       Call Source:    Initiated
  Location/Address:    MAIN ST
"""


def log_text(*entries: str, log_date: str = "05/11/2026") -> str:
    return HEADER.format(date=log_date) + "".join(entries)


def add_url(session, canonical_url="https://example.com/2026-05-11", **columns):
    values = {
        "canonical_url": canonical_url,
        "log_date": date(2026, 5, 11),
        "state": "in_progress",
        "created_at": datetime(2026, 5, 12),
        **columns,
    }
    url = PdfUrl(**values)
    session.add(url)
    session.commit()
    return url


def entries(session) -> dict[str, LogEntry]:
    session.expire_all()
    return {entry.case_number: entry for entry in session.scalars(select(LogEntry))}


def test_stores_each_entry_with_its_source_and_log_date(db_session):
    url = add_url(db_session)

    counts = ingest_log_text(db_session, url, log_text(HARASSMENT, PATROL))

    assert counts == IngestCounts(
        parsed=2,
        inserted=2,
        updated=0,
        unchanged=0,
        skipped=0,
        missing=0,
        header_lines=2,
    )
    stored = entries(db_session)
    assert set(stored) == {"26-13339", "26-13340"}
    harassment = stored["26-13339"]
    assert harassment.source_url == "https://example.com/2026-05-11"
    assert harassment.log_date == date(2026, 5, 11)
    assert harassment.incident_type == "Telephone Harassment"
    assert harassment.raw_text.startswith("26-13339")
    assert harassment.created_at == harassment.updated_at


def test_log_date_comes_from_the_text_when_the_url_has_none(db_session):
    url = add_url(db_session, log_date=None)

    ingest_log_text(db_session, url, log_text(HARASSMENT, log_date="05/13/2026"))

    assert entries(db_session)["26-13339"].log_date == date(2026, 5, 13)


def test_second_ingest_of_the_same_text_changes_no_row(db_session):
    url = add_url(db_session)
    text = log_text(HARASSMENT, PATROL)
    ingest_log_text(db_session, url, text)
    db_session.commit()
    before = {case: entry.updated_at for case, entry in entries(db_session).items()}

    counts = ingest_log_text(db_session, url, text)

    assert (counts.inserted, counts.updated, counts.unchanged) == (0, 0, 2)
    after = {case: entry.updated_at for case, entry in entries(db_session).items()}
    assert after == before


def test_changed_text_updates_the_entry_and_moves_updated_at(db_session):
    url = add_url(db_session)
    ingest_log_text(db_session, url, log_text(HARASSMENT))
    db_session.commit()
    created_at = entries(db_session)["26-13339"].created_at

    moved = HARASSMENT.replace("TIMBERWOOD DR", "HANOVER ST")
    counts = ingest_log_text(db_session, url, log_text(moved))

    assert (counts.inserted, counts.updated, counts.unchanged) == (0, 1, 0)
    entry = entries(db_session)["26-13339"]
    assert entry.location == "HANOVER ST"
    assert entry.created_at == created_at
    assert entry.updated_at > created_at


def test_entry_stored_before_these_columns_existed_is_updated(db_session):
    url = add_url(db_session)
    old = datetime(2026, 6, 7, 17, 48)
    db_session.add(
        LogEntry(
            case_number="26-13339",
            source_url=url.canonical_url,
            log_date=date(2026, 5, 11),
            incident_type="Telephone Harassment Incident Report Taken",
            raw_text="old text",
            scraped_at=old,
            created_at=old,
            updated_at=old,
        )
    )
    db_session.commit()

    counts = ingest_log_text(db_session, url, log_text(HARASSMENT))

    assert counts.updated == 1
    entry = entries(db_session)["26-13339"]
    assert entry.incident_type == "Telephone Harassment"
    assert entry.created_at == old


def test_later_log_date_wins_when_the_older_pdf_is_ingested_second(db_session):
    newer = add_url(
        db_session, "https://example.com/2026-05-12", log_date=date(2026, 5, 12)
    )
    older = add_url(
        db_session, "https://example.com/2026-05-11", log_date=date(2026, 5, 11)
    )
    corrected = HARASSMENT.replace("TIMBERWOOD DR", "HANOVER ST")
    ingest_log_text(db_session, newer, log_text(corrected, log_date="05/12/2026"))
    db_session.commit()
    updated_at = entries(db_session)["26-13339"].updated_at

    counts = ingest_log_text(db_session, older, log_text(HARASSMENT))

    assert (counts.inserted, counts.updated, counts.unchanged) == (0, 0, 1)
    entry = entries(db_session)["26-13339"]
    assert entry.location == "HANOVER ST"
    assert entry.source_url == "https://example.com/2026-05-12"
    assert entry.log_date == date(2026, 5, 12)
    assert entry.updated_at == updated_at


def test_later_log_date_replaces_the_older_pdfs_values(db_session):
    older = add_url(
        db_session, "https://example.com/2026-05-11", log_date=date(2026, 5, 11)
    )
    newer = add_url(
        db_session, "https://example.com/2026-05-12", log_date=date(2026, 5, 12)
    )
    ingest_log_text(db_session, older, log_text(HARASSMENT))
    db_session.commit()

    corrected = HARASSMENT.replace("TIMBERWOOD DR", "HANOVER ST")
    counts = ingest_log_text(
        db_session, newer, log_text(corrected, log_date="05/12/2026")
    )

    assert counts.updated == 1
    entry = entries(db_session)["26-13339"]
    assert entry.location == "HANOVER ST"
    assert entry.source_url == "https://example.com/2026-05-12"


def test_invalid_entry_is_skipped_and_the_rest_are_stored(db_session, monkeypatch):
    url = add_url(db_session)
    monkeypatch.setattr(
        "ingest.police_log.parse_log_entries",
        lambda text: [
            {"case_number": "26-13339", "raw_text": "26-13339 ..."},
            {"case_number": "26-13340", "raw_text": None},
            {"case_number": None, "raw_text": "no case number"},
            {"case_number": "26-13342", "raw_text": "26-13342 ..."},
        ],
    )

    counts = ingest_log_text(db_session, url, log_text())

    assert (counts.parsed, counts.inserted, counts.skipped) == (4, 2, 2)
    assert set(entries(db_session)) == {"26-13339", "26-13342"}


def test_header_lines_count_case_number_lines_the_parser_did_not_read(db_session):
    url = add_url(db_session)
    unreadable = "26-13341        late Phone - Noise Complaint Log Information\n"

    counts = ingest_log_text(db_session, url, log_text(HARASSMENT, unreadable))

    assert (counts.parsed, counts.header_lines) == (1, 2)


def test_entry_missing_from_a_later_parse_is_kept_and_flagged(db_session):
    url = add_url(db_session)
    ingest_log_text(db_session, url, log_text(HARASSMENT, PATROL))
    db_session.commit()

    counts = ingest_log_text(db_session, url, log_text(HARASSMENT))

    assert counts.missing == 1
    stored = entries(db_session)
    assert stored["26-13340"].missing_from_parse is True
    assert stored["26-13339"].missing_from_parse is False


def test_missing_flag_clears_when_the_entry_returns(db_session):
    url = add_url(db_session)
    ingest_log_text(db_session, url, log_text(HARASSMENT, PATROL))
    ingest_log_text(db_session, url, log_text(HARASSMENT))
    db_session.commit()
    updated_at = entries(db_session)["26-13340"].updated_at

    counts = ingest_log_text(db_session, url, log_text(HARASSMENT, PATROL))

    assert (counts.missing, counts.unchanged) == (0, 2)
    patrol = entries(db_session)["26-13340"]
    assert patrol.missing_from_parse is False
    assert patrol.updated_at == updated_at


def test_parser_version_bump_alone_does_not_move_updated_at(db_session, monkeypatch):
    url = add_url(db_session)
    ingest_log_text(db_session, url, log_text(HARASSMENT))
    db_session.commit()
    updated_at = entries(db_session)["26-13339"].updated_at
    monkeypatch.setattr("ingest.police_log.PARSER_VERSION", PARSER_VERSION + 1)

    counts = ingest_log_text(db_session, url, log_text(HARASSMENT))

    assert counts.unchanged == 1
    assert entries(db_session)["26-13339"].updated_at == updated_at


# --- ingest_pdf_url: the outcome on the URL record ---


def test_url_is_completed_with_its_counts_and_text(db_session):
    url = add_url(db_session)
    text = log_text(HARASSMENT, PATROL)

    ingest_pdf_url(db_session, url, text)
    db_session.commit()

    db_session.refresh(url)
    assert url.state == "complete"
    assert url.error_kind is None
    assert url.error_message is None
    assert (url.parsed_count, url.stored_count, url.skipped_count) == (2, 2, 0)
    assert url.header_lines == 2
    assert url.parser_version == PARSER_VERSION
    assert url.raw_text == text
    assert url.completed_at is not None


def test_pdf_with_no_entries_is_a_parse_error_that_keeps_its_text(db_session):
    url = add_url(db_session)

    ingest_pdf_url(db_session, url, "No date header here, will not parse")
    db_session.commit()

    db_session.refresh(url)
    assert url.state == "error"
    assert url.error_kind == "parse"
    assert url.error_message == "No entries stored from PDF"
    assert url.raw_text == "No date header here, will not parse"
    assert (url.parsed_count, url.stored_count) == (0, 0)


def test_error_url_is_completed_once_it_stores_an_entry(db_session):
    url = add_url(db_session, state="error", error_kind="parse", error_message="x")

    ingest_pdf_url(db_session, url, log_text(HARASSMENT))
    db_session.commit()

    db_session.refresh(url)
    assert (url.state, url.error_kind, url.error_message) == ("complete", None, None)


@pytest.mark.parametrize(
    ("counts", "stored"),
    [
        (IngestCounts(3, 1, 1, 1, 0, 0, 3), 3),
        (IngestCounts(3, 0, 0, 0, 3, 0, 3), 0),
    ],
)
def test_stored_counts_every_entry_that_is_in_the_table(counts, stored):
    assert counts.stored == stored
