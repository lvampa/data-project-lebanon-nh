"""The export's stats and incidents queries, run against the test database.

The queries live in files that report-gen includes, so this is the same SQL.
"""

from datetime import date, datetime
from pathlib import Path

import pytest
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import select, text

SQL = Path(__file__).resolve().parents[3] / "tools" / "report-gen" / "src" / "sql"
SINCE = date(2026, 1, 1)
NOW = datetime(2026, 11, 19)


def query(name: str) -> str:
    # report-gen binds $1 as the first day, and $2 as a row limit.
    return (SQL / name).read_text().replace("$1", ":since").replace("$2", ":limit")


def add_entry(
    session,
    number: int,
    log_date: date,
    incident_type: str,
    reported_at: datetime | None,
    plain: bool = True,
) -> None:
    known = session.scalar(
        select(IncidentTypeCategory.id).where(
            IncidentTypeCategory.raw_incident_type == incident_type
        )
    )
    if plain and known is None:
        session.add(
            IncidentTypeCategory(
                raw_incident_type=incident_type,
                normalized_type=incident_type,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.flush()
    session.add(
        LogEntry(
            case_number=f"case-{number}",
            source_url="https://example.com/log.pdf",
            log_date=log_date,
            reported_at=reported_at,
            incident_type=incident_type,
            created_at=NOW,
            updated_at=NOW,
        )
    )


@pytest.fixture
def three_days(db_session):
    # Dec 31 is out. Jan 1, a Thursday, is in. June 1, a Monday, has no reported time.
    add_entry(
        db_session, 1, date(2025, 12, 31), "Alarm", datetime(2025, 12, 31, 23, 59)
    )
    add_entry(db_session, 2, date(2026, 1, 1), "Alarm", datetime(2026, 1, 1))
    add_entry(db_session, 3, date(2026, 6, 1), "Noise", None)
    db_session.flush()


def test_the_total_counts_entries_by_log_date_from_the_day(db_session, three_days):
    total = db_session.scalar(text(query("stats_total.sql")), {"since": SINCE})

    assert total == 2


def test_by_type_counts_entries_by_log_date_from_the_day(db_session, three_days):
    rows = db_session.execute(text(query("stats_by_type.sql")), {"since": SINCE}).all()

    assert sorted(tuple(row) for row in rows) == [("Alarm", 1), ("Noise", 1)]


def test_by_weekday_counts_only_entries_with_a_reported_time(db_session, three_days):
    rows = db_session.execute(
        text(query("stats_by_weekday.sql")), {"since": SINCE}
    ).all()

    # Thursday 1 January only. The Dec 31 entry is before the day, and the June one
    # has no reported time to take a weekday from.
    assert [tuple(row) for row in rows] == [(4.0, 1)]


def test_by_hour_counts_the_hour_of_the_reported_time(db_session, three_days):
    add_entry(db_session, 4, date(2026, 1, 2), "Alarm", datetime(2026, 1, 2, 16, 30))
    add_entry(db_session, 5, date(2026, 1, 2), "Alarm", datetime(2026, 1, 2, 16, 59))
    db_session.flush()

    rows = db_session.execute(text(query("stats_by_hour.sql")), {"since": SINCE}).all()

    # Midnight on Jan 1 and two calls in the 4 pm hour. The entry with no reported
    # time has no hour, and the Dec 31 entry is before the day.
    assert [tuple(row) for row in rows] == [(0, 1), (16, 2)]


def test_incidents_leave_out_before_the_day_and_put_unreported_ones_last(
    db_session, three_days
):
    rows = db_session.execute(
        text(query("incidents.sql")), {"since": SINCE, "limit": 10}
    ).all()

    assert [row.case_number for row in rows] == ["case-2", "case-3"]


# --- the public rules ---


def test_a_type_with_no_plain_name_is_counted_as_other(db_session):
    add_entry(db_session, 1, date(2026, 6, 1), "DEP INFO - M-ARTHUR", None, plain=False)
    add_entry(db_session, 2, date(2026, 6, 1), "Alarm", None)
    db_session.flush()

    rows = db_session.execute(text(query("stats_by_type.sql")), {"since": SINCE}).all()

    assert sorted(tuple(row) for row in rows) == [("Alarm", 1), ("Other", 1)]


def test_other_is_last_whatever_its_count(db_session):
    for number in range(5):
        add_entry(
            db_session, number, date(2026, 6, 1), f"RAW {number}", None, plain=False
        )
    add_entry(db_session, 10, date(2026, 6, 1), "Alarm", None)
    db_session.flush()

    rows = db_session.execute(text(query("stats_by_type.sql")), {"since": SINCE}).all()

    assert [tuple(row) for row in rows] == [("Alarm", 1), ("Other", 5)]


def test_other_is_listed_after_the_twenty_busiest_names(db_session):
    for number in range(25):
        add_entry(db_session, number, date(2026, 6, 1), f"Type {number:02}", None)
    for number in range(30, 40):
        add_entry(
            db_session, number, date(2026, 6, 1), f"RAW {number}", None, plain=False
        )
    db_session.flush()

    rows = db_session.execute(text(query("stats_by_type.sql")), {"since": SINCE}).all()

    names = [row[0] for row in rows]
    assert len(names) == 21
    assert names[-1] == "Other"
    assert "Other" not in names[:-1]


def test_the_total_still_counts_every_entry(db_session):
    add_entry(db_session, 1, date(2026, 6, 1), "Alarm", None)
    add_entry(db_session, 2, date(2026, 6, 1), "UNNAMED", None, plain=False)
    db_session.flush()

    assert db_session.scalar(text(query("stats_total.sql")), {"since": SINCE}) == 2


def test_incidents_publish_the_public_location(db_session):
    from postgres.models.address_normalization import AddressNormalization

    for raw, columns in [
        ("SHOP", {"normalized_address": "Shop, Main St"}),
        ("PERSON", {"normalized_address": "F and Child", "names_person": True}),
        (
            "PERSON NO STREET",
            {"normalized_address": "F and Child", "names_person": True, "street": None},
        ),
    ]:
        db_session.add(
            AddressNormalization(
                raw_address=raw,
                created_at=NOW,
                updated_at=NOW,
                **{
                    "kind": "place",
                    "street": "MAIN ST",
                    "source": "ai",
                    **columns,
                },
            )
        )
    db_session.flush()
    for number, location in enumerate(
        ["SHOP", "PERSON", "PERSON NO STREET", "NEVER SEEN"]
    ):
        add_entry(
            db_session, number, date(2026, 6, 1), "Alarm", datetime(2026, 6, 1, number)
        )
        db_session.execute(
            text("UPDATE log_entries SET location = :l WHERE case_number = :c"),
            {"l": location, "c": f"case-{number}"},
        )

    rows = (
        db_session.execute(text(query("incidents.sql")), {"since": SINCE, "limit": 10})
        .mappings()
        .all()
    )

    by_case = {row["case_number"]: row["location"] for row in rows}
    assert by_case == {
        "case-0": "Shop, Main St",
        "case-1": "MAIN ST",
        "case-2": None,
        "case-3": None,
    }
