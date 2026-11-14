from datetime import date, datetime

from maintenance import police_logs
from postgres.models.log_entry import LogEntry
from postgres.models.pdf_url import PdfUrl
from sqlalchemy import select

URL_A = "https://example.com/2026-05-11"
URL_B = "https://example.com/2026-05-12"
URL_C = "https://example.com/2026-05-13"


def add_url(session, canonical_url: str, day: date, **columns) -> PdfUrl:
    url = PdfUrl(
        canonical_url=canonical_url,
        log_date=day,
        created_at=datetime(2026, 5, 12),
        **columns,
    )
    session.add(url)
    session.commit()
    return url


def add_entry(session, case_number: str, **columns) -> None:
    session.add(
        LogEntry(
            case_number=case_number,
            source_url=URL_A,
            log_date=date(2026, 5, 11),
            created_at=datetime(2026, 5, 12),
            updated_at=datetime(2026, 5, 12),
            **columns,
        )
    )
    session.commit()


def test_errors_lists_each_url_in_error_with_its_reason(db_session, capsys):
    add_url(db_session, URL_A, date(2026, 5, 11), state="complete")
    add_url(
        db_session,
        URL_B,
        date(2026, 5, 12),
        state="error",
        error_kind="download",
        error_message="Request failed: DNSLookupError",
        attempts=3,
    )
    add_url(
        db_session,
        URL_C,
        date(2026, 5, 13),
        state="error",
        error_kind="parse",
        error_message="No entries stored from PDF",
        attempts=1,
    )

    assert police_logs.main(["errors"]) == 0

    out = capsys.readouterr().out
    assert URL_B in out
    assert "download" in out
    assert "Request failed: DNSLookupError" in out
    assert "attempts 3" in out
    assert URL_C in out
    assert "No entries stored from PDF" in out
    assert URL_A not in out


def test_errors_says_so_when_there_are_none(db_session, capsys):
    add_url(db_session, URL_A, date(2026, 5, 11), state="complete")

    assert police_logs.main(["errors"]) == 0

    assert "No URL records in error." in capsys.readouterr().out


def test_reset_returns_the_chosen_urls_to_pending_with_a_fresh_attempt_count(
    db_session, capsys
):
    first = add_url(
        db_session,
        URL_A,
        date(2026, 5, 11),
        state="error",
        error_kind="download",
        error_message="Claim expired",
        attempts=3,
    )
    second = add_url(
        db_session, URL_B, date(2026, 5, 12), state="error", error_kind="parse"
    )
    untouched = add_url(
        db_session, URL_C, date(2026, 5, 13), state="error", error_kind="save"
    )

    assert police_logs.main(["reset", URL_A, URL_B]) == 0

    db_session.expire_all()
    assert (first.state, first.attempts) == ("pending", 0)
    assert (first.error_kind, first.error_message) == (None, None)
    assert second.state == "pending"
    assert untouched.state == "error"
    assert "Reset 2 URL records to pending." in capsys.readouterr().out


def test_reset_leaves_a_url_that_is_not_in_error_and_exits_non_zero(db_session, capsys):
    complete = add_url(db_session, URL_A, date(2026, 5, 11), state="complete")

    assert police_logs.main(["reset", URL_A]) == 1

    db_session.expire_all()
    assert complete.state == "complete"
    assert f"{URL_A}: not in error" in capsys.readouterr().err


def test_reset_reports_an_unknown_url_but_still_resets_the_others(db_session, capsys):
    known = add_url(db_session, URL_A, date(2026, 5, 11), state="error")

    assert police_logs.main(["reset", "https://example.com/nope", URL_A]) == 1

    db_session.expire_all()
    assert known.state == "pending"
    assert "https://example.com/nope: no such URL record" in capsys.readouterr().err


def test_unmatched_dispositions_lists_the_entries_marked_unmatched(db_session, capsys):
    add_entry(
        db_session,
        "26-1",
        incident_type="Suspicious Person Frobnicated",
        disposition_unmatched=True,
    )
    add_entry(
        db_session,
        "26-2",
        incident_type="Suspicious Person",
        disposition="Advised",
    )

    assert police_logs.main(["unmatched-dispositions"]) == 0

    out = capsys.readouterr().out
    assert "26-1" in out
    assert "2026-05-11" in out
    assert "Suspicious Person Frobnicated" in out
    assert "26-2" not in out


def test_unmatched_dispositions_says_so_when_there_are_none(db_session, capsys):
    add_entry(db_session, "26-2", incident_type="Suspicious Person")

    assert police_logs.main(["unmatched-dispositions"]) == 0

    assert "No entries with an unmatched disposition." in capsys.readouterr().out


def test_reset_does_not_touch_any_log_entry(db_session):
    add_entry(db_session, "26-1", incident_type="Noise")
    add_url(db_session, URL_A, date(2026, 5, 11), state="error")

    police_logs.main(["reset", URL_A])

    db_session.expire_all()
    assert db_session.scalars(select(LogEntry.incident_type)).all() == ["Noise"]
