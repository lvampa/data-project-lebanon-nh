import itertools
import socket
from datetime import UTC, date, datetime, timedelta

import pytest
from ingest import police_log as ingest_module
from ingest.lock import police_log_lock
from maintenance import reprocess_police_logs
from maintenance.reprocess_police_logs import ReprocessCounts, reprocess
from mongo.archive import ArchivedResponse, RawArchive, content_hash
from parsers.police_log import EXTRACTOR_VERSION, PARSER_VERSION
from postgres.models.address_normalization import AddressNormalization
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from postgres.models.pdf_url import PdfUrl
from pymongo.errors import ServerSelectionTimeoutError
from sqlalchemy import select

PDF_SOURCE = "police_log_pdf"
ENTRY_TEXT_SOURCE = "police_log_entry_text"

HEADER = """\
For Date: {date}  -  Monday
Call   Number   Time   Call   Reason   Action
"""

HARASSMENT = """\
26-13339        0106 Phone - Telephone Harassment Incident Report Taken
       Call Source:    Telephone
  Location/Address:    TIMBERWOOD DR
"""

HARASSMENT_WITH_VICINITY = """\
26-13339        0106 Phone - Telephone Harassment Incident Report Taken
       Call Source:    Telephone
      Vicinity of:    I-89 NB MM 18
"""

PATROL = """\
26-13340        0212 Initiated - Directed Patrol Log Information
       Call Source:    Initiated
  Location/Address:    MAIN ST
"""


def log_text(*entries: str, day: str = "05/11/2026") -> str:
    return HEADER.format(date=day) + "".join(entries)


@pytest.fixture(autouse=True)
def text_is_the_stored_body(monkeypatch):
    """Archived bodies in these tests are the log text itself, so no real PDF is needed."""
    monkeypatch.setattr(
        reprocess_police_logs, "extract_pdf_text", lambda body: body.decode()
    )


@pytest.fixture
def archive(raw_sources) -> RawArchive:
    return RawArchive(raw_sources, batch_size=1)


_fetches = itertools.count()


def archived_response(url: str, body: bytes) -> ArchivedResponse:
    # Each call is a later fetch, so the newest version is the last one added.
    fetched_at = datetime(2026, 11, 6, tzinfo=UTC) + timedelta(minutes=next(_fetches))
    return ArchivedResponse(
        url=url,
        status=200,
        content_type="application/pdf",
        body=body,
        fetched_at=fetched_at,
        spider="process_urls",
    )


def archive_pdf(archive: RawArchive, url: str, text: str) -> str:
    archive.add(PDF_SOURCE, url, archived_response(url, text.encode()))
    return content_hash(PDF_SOURCE, text.encode())


def add_url(session, canonical_url: str, *, day: date, **columns) -> PdfUrl:
    url = PdfUrl(
        canonical_url=canonical_url,
        log_date=day,
        state=columns.pop("state", "complete"),
        created_at=datetime(2026, 5, 12),
        **columns,
    )
    session.add(url)
    session.commit()
    return url


def stored(session) -> dict[str, LogEntry]:
    session.expire_all()
    return {row.case_number: row for row in session.scalars(select(LogEntry))}


def counts(**overrides: int) -> ReprocessCounts:
    return ReprocessCounts(**{**ReprocessCounts().__dict__, **overrides})


URL_A = "https://example.com/2026-05-11"
URL_B = "https://example.com/2026-05-12"


def test_it_parses_the_newest_archived_version_and_stores_the_entries(
    db_session, archive
):
    url = add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(archive, URL_A, log_text(HARASSMENT, PATROL))

    result = reprocess(archive, None, None)

    assert result == counts(urls=1, inserted=2)
    assert set(stored(db_session)) == {"26-13339", "26-13340"}
    db_session.refresh(url)
    assert url.state == "complete"
    assert url.stored_count == 2


def test_a_parser_fix_updates_an_entry_already_stored(db_session, archive):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(archive, URL_A, log_text(HARASSMENT))
    reprocess(archive, None, None)
    assert stored(db_session)["26-13339"].location == "TIMBERWOOD DR"

    # The same PDF read by a later, fixed parser: the archive's newest version wins.
    archive_pdf(archive, URL_A, log_text(HARASSMENT_WITH_VICINITY))
    result = reprocess(archive, None, None)

    assert result == counts(urls=1, updated=1)
    assert stored(db_session)["26-13339"].location == "I-89 NB MM 18"


def test_a_second_run_changes_no_entry_and_does_not_move_updated_at(
    db_session, archive
):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(archive, URL_A, log_text(HARASSMENT, PATROL))
    reprocess(archive, None, None)
    first = {k: v.updated_at for k, v in stored(db_session).items()}

    result = reprocess(archive, None, None)

    assert result == counts(urls=1, unchanged=2)
    assert {k: v.updated_at for k, v in stored(db_session).items()} == first


def test_a_parser_version_bump_alone_does_not_move_updated_at(
    db_session, archive, monkeypatch
):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(archive, URL_A, log_text(HARASSMENT))
    reprocess(archive, None, None)
    before = stored(db_session)["26-13339"].updated_at

    monkeypatch.setattr(ingest_module, "PARSER_VERSION", 99)
    result = reprocess(archive, None, None)

    entry = stored(db_session)["26-13339"]
    assert result == counts(urls=1, unchanged=1)
    assert (entry.parser_version, entry.updated_at) == (99, before)


def test_an_error_record_that_now_stores_entries_is_marked_complete(
    db_session, archive
):
    url = add_url(
        db_session,
        URL_A,
        day=date(2026, 5, 11),
        state="error",
        error_kind="parse",
        error_message="No entries stored from PDF",
    )
    expected_hash = archive_pdf(archive, URL_A, log_text(HARASSMENT))

    reprocess(archive, None, None)

    db_session.refresh(url)
    assert (url.state, url.error_kind, url.error_message) == ("complete", None, None)
    assert url.content_hash == expected_hash
    assert url.parser_version == PARSER_VERSION
    assert url.extractor_version == EXTRACTOR_VERSION


def test_pending_and_in_progress_records_are_left_alone(db_session, archive):
    add_url(db_session, URL_A, day=date(2026, 5, 11), state="pending")
    add_url(db_session, URL_B, day=date(2026, 5, 12), state="in_progress")
    archive_pdf(archive, URL_A, log_text(HARASSMENT))

    result = reprocess(archive, None, None)

    assert result == counts()
    assert stored(db_session) == {}


def test_a_date_range_picks_only_the_records_inside_it(db_session, archive):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    add_url(db_session, URL_B, day=date(2026, 5, 12))
    archive_pdf(archive, URL_A, log_text(HARASSMENT))
    archive_pdf(archive, URL_B, log_text(PATROL, day="05/12/2026"))

    result = reprocess(archive, date(2026, 5, 12), date(2026, 5, 12))

    assert result == counts(urls=1, inserted=1)
    assert set(stored(db_session)) == {"26-13340"}


def test_records_are_worked_in_log_date_order(db_session, archive):
    # Inserted newest first, so id order is the wrong order.
    add_url(db_session, URL_B, day=date(2026, 5, 12))
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(archive, URL_A, log_text(HARASSMENT))
    archive_pdf(archive, URL_B, log_text(HARASSMENT, day="05/12/2026"))

    reprocess(archive, None, None)

    # The same case number is in both PDFs; the later log date has to win.
    assert stored(db_session)["26-13339"].log_date == date(2026, 5, 12)
    assert stored(db_session)["26-13339"].source_url == URL_B


def test_a_record_with_no_archived_version_goes_back_to_pending(db_session, archive):
    url = add_url(
        db_session,
        URL_A,
        day=date(2026, 5, 11),
        state="error",
        error_kind="parse",
        error_message="No entries stored from PDF",
    )

    result = reprocess(archive, None, None)

    assert result == counts(urls=1, requeued=1)
    db_session.refresh(url)
    assert url.state == "pending"
    assert url.error_kind is None
    assert stored(db_session) == {}


def test_a_truncated_pdf_counts_as_having_no_archived_version(
    db_session, archive, raw_sources
):
    url = add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(archive, URL_A, log_text(HARASSMENT))
    raw_sources.update_many({"source": PDF_SOURCE}, {"$set": {"truncated": True}})

    result = reprocess(archive, None, None)

    assert result == counts(urls=1, requeued=1)
    db_session.refresh(url)
    assert url.state == "pending"


def test_an_entry_the_new_parse_no_longer_finds_is_kept_and_counted(
    db_session, archive
):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(archive, URL_A, log_text(HARASSMENT, PATROL))
    reprocess(archive, None, None)

    archive_pdf(archive, URL_A, log_text(HARASSMENT))
    result = reprocess(archive, None, None)

    assert result == counts(urls=1, unchanged=1, missing=1)
    assert stored(db_session)["26-13340"].missing_from_parse is True


def test_it_does_not_change_or_delete_any_normalization(db_session, archive):
    now = datetime(2026, 5, 12)
    db_session.add_all(
        [
            AddressNormalization(
                raw_address="TIMBERWOOD DR",
                normalized_address="TIMBERWOOD DR",
                created_at=now,
                updated_at=now,
            ),
            IncidentTypeCategory(
                raw_incident_type="Telephone Harassment",
                category="Harassment",
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db_session.commit()
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(archive, URL_A, log_text(HARASSMENT))

    def normalizations() -> list[tuple[object, ...]]:
        db_session.expire_all()
        return [
            *db_session.execute(select(AddressNormalization)).all(),
            *db_session.execute(select(IncidentTypeCategory)).all(),
        ]

    before = normalizations()
    reprocess(archive, None, None)

    assert normalizations() == before


def test_each_entrys_raw_text_is_written_to_the_archive_and_a_rerun_adds_none(
    db_session, archive, raw_sources
):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(archive, URL_A, log_text(HARASSMENT, PATROL))

    reprocess(archive, None, None)
    first = raw_sources.count_documents({"source": ENTRY_TEXT_SOURCE})
    reprocess(archive, None, None)

    assert first == 2
    assert raw_sources.count_documents({"source": ENTRY_TEXT_SOURCE}) == 2
    [version] = raw_sources.find(
        {"source": ENTRY_TEXT_SOURCE, "source_key": "26-13340"}
    )
    assert version["seen_count"] == 2


def test_one_records_failure_does_not_stop_the_others(db_session, archive, monkeypatch):
    bad = add_url(db_session, URL_A, day=date(2026, 5, 11))
    add_url(db_session, URL_B, day=date(2026, 5, 12))
    archive_pdf(archive, URL_A, "unreadable")
    archive_pdf(archive, URL_B, log_text(PATROL, day="05/12/2026"))

    def extract(body: bytes) -> str:
        if body == b"unreadable":
            raise ValueError("EOF marker not found")
        return body.decode()

    monkeypatch.setattr(reprocess_police_logs, "extract_pdf_text", extract)

    result = reprocess(archive, None, None)

    assert result == counts(urls=2, inserted=1, failed=1)
    assert set(stored(db_session)) == {"26-13340"}
    db_session.refresh(bad)
    assert bad.state == "complete"


def test_the_archive_going_down_mid_run_stops_the_run_and_keeps_what_was_done(
    db_session, archive, monkeypatch
):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    second = add_url(db_session, URL_B, day=date(2026, 5, 12))
    archive_pdf(archive, URL_A, log_text(HARASSMENT))
    archive_pdf(archive, URL_B, log_text(PATROL, day="05/12/2026"))
    real_newest = RawArchive.newest
    calls = 0

    def newest(self, source, source_key):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise ServerSelectionTimeoutError("archive went away")
        return real_newest(self, source, source_key)

    monkeypatch.setattr(RawArchive, "newest", newest)

    result = reprocess(archive, None, None)

    assert result == counts(urls=2, inserted=1, failed=1, stopped_early=1)
    assert set(stored(db_session)) == {"26-13339"}
    db_session.refresh(second)
    # An archive that cannot answer is not an archive with no original.
    assert second.state == "complete"


def test_a_complete_record_that_now_reparses_to_no_entries_becomes_an_error(
    db_session, archive
):
    # Current behaviour, pinned so a change is a decision: the ingest marks a PDF with
    # no stored entries as error. Its entries are kept, flagged as missing from the parse.
    url = add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(archive, URL_A, log_text(HARASSMENT))
    reprocess(archive, None, None)

    archive_pdf(archive, URL_A, "not a police log at all")
    reprocess(archive, None, None)

    db_session.refresh(url)
    assert (url.state, url.error_kind) == ("error", "parse")
    assert stored(db_session)["26-13339"].missing_from_parse is True


# --- the command ---


def closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_main_reprocesses_everything_with_all(db_session, raw_sources, capsys):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(RawArchive(raw_sources, batch_size=1), URL_A, log_text(HARASSMENT))

    assert reprocess_police_logs.main(["--all"]) == 0

    assert set(stored(db_session)) == {"26-13339"}
    assert "1 inserted" in capsys.readouterr().out


def test_main_takes_a_date_range(db_session, raw_sources):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    add_url(db_session, URL_B, day=date(2026, 5, 12))
    archive = RawArchive(raw_sources, batch_size=1)
    archive_pdf(archive, URL_A, log_text(HARASSMENT))
    archive_pdf(archive, URL_B, log_text(PATROL, day="05/12/2026"))

    status = reprocess_police_logs.main(["--from", "2026-05-12", "--to", "2026-05-12"])

    assert status == 0
    assert set(stored(db_session)) == {"26-13340"}


@pytest.mark.parametrize(
    "argv",
    [[], ["--from", "2026-05-11"], ["--all", "--from", "2026-05-11"]],
    ids=["no_scope", "from_without_to", "all_with_a_range"],
)
def test_main_needs_all_or_a_full_range(argv):
    with pytest.raises(SystemExit):
        reprocess_police_logs.main(argv)


def test_main_says_so_when_the_archive_stopped_answering(
    db_session, raw_sources, monkeypatch, capsys
):
    add_url(db_session, URL_A, day=date(2026, 5, 11))

    def newest(self, source, source_key):
        raise ServerSelectionTimeoutError("archive went away")

    monkeypatch.setattr(RawArchive, "newest", newest)

    assert reprocess_police_logs.main(["--all"]) == 1

    assert "stopped early" in capsys.readouterr().out


def test_main_exits_non_zero_when_a_record_failed(db_session, raw_sources, monkeypatch):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(RawArchive(raw_sources, batch_size=1), URL_A, "unreadable")

    def extract(body: bytes) -> str:
        raise ValueError("EOF marker not found")

    monkeypatch.setattr(reprocess_police_logs, "extract_pdf_text", extract)

    assert reprocess_police_logs.main(["--all"]) == 1


def test_main_stops_before_any_change_when_the_archive_is_unreachable(
    db_session, monkeypatch, capsys
):
    url = add_url(
        db_session, URL_A, day=date(2026, 5, 11), state="error", error_kind="parse"
    )
    monkeypatch.setenv("MONGO_HOST", "127.0.0.1")
    monkeypatch.setenv("MONGO_PORT", str(closed_port()))

    assert reprocess_police_logs.main(["--all"]) == 1

    db_session.refresh(url)
    assert (url.state, url.error_kind) == ("error", "parse")
    assert "archive" in capsys.readouterr().err.lower()


def test_main_does_not_run_while_another_police_log_job_holds_the_lock(
    db_session, test_engine, raw_sources, capsys
):
    add_url(db_session, URL_A, day=date(2026, 5, 11))
    archive_pdf(RawArchive(raw_sources, batch_size=1), URL_A, log_text(HARASSMENT))

    with police_log_lock(test_engine) as acquired:
        assert acquired

        assert reprocess_police_logs.main(["--all"]) == 1

    assert stored(db_session) == {}
    assert "Another police log job" in capsys.readouterr().err
