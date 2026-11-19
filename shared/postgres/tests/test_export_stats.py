"""The export's stats and incidents queries, run against the test database.

The queries live in files that report-gen includes, so this is the same SQL.
"""

from datetime import date, datetime
from pathlib import Path

import pytest
from postgres.models.log_entry import LogEntry
from sqlalchemy import text

SQL = Path(__file__).resolve().parents[3] / "tools" / "report-gen" / "src" / "sql"
SINCE = date(2026, 1, 1)
NOW = datetime(2026, 11, 19)
BEFORE = datetime(2025, 12, 31, 23, 59)
ON_THE_DAY = datetime(2026, 1, 1)  # a Thursday


def query(name: str) -> str:
    # report-gen binds $1 as the first day, and $2 as a row limit.
    return (SQL / name).read_text().replace("$1", ":since").replace("$2", ":limit")


def add_entry(session, number: int, reported_at: datetime, incident_type: str) -> None:
    session.add(
        LogEntry(
            case_number=f"case-{number}",
            source_url="https://example.com/log.pdf",
            log_date=reported_at.date(),
            reported_at=reported_at,
            incident_type=incident_type,
            created_at=NOW,
            updated_at=NOW,
        )
    )


@pytest.fixture
def two_years(db_session):
    add_entry(db_session, 1, BEFORE, "Alarm")
    add_entry(db_session, 2, ON_THE_DAY, "Alarm")
    add_entry(db_session, 3, datetime(2026, 6, 1), "Noise")
    db_session.flush()


def test_the_total_counts_only_entries_since_the_day(db_session, two_years):
    total = db_session.scalar(text(query("stats_total.sql")), {"since": SINCE})

    assert total == 2


def test_by_type_counts_only_entries_since_the_day(db_session, two_years):
    rows = db_session.execute(text(query("stats_by_type.sql")), {"since": SINCE}).all()

    assert sorted(tuple(row) for row in rows) == [("Alarm", 1), ("Noise", 1)]


def test_by_weekday_counts_only_entries_since_the_day(db_session, two_years):
    rows = db_session.execute(
        text(query("stats_by_weekday.sql")), {"since": SINCE}
    ).all()

    # Thursday 1 January, and Monday 1 June. The Wednesday entry is before the day.
    assert sorted(tuple(row) for row in rows) == [(1.0, 1), (4.0, 1)]


def test_incidents_leave_out_entries_before_the_day_and_keep_the_day(
    db_session, two_years
):
    rows = db_session.execute(
        text(query("incidents.sql")), {"since": SINCE, "limit": 10}
    ).all()

    assert [row.case_number for row in rows] == ["case-3", "case-2"]
