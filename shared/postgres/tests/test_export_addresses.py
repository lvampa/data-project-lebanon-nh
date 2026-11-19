"""The export's address query, run against the test database.

The query lives in a file that report-gen includes, so this is the same SQL.
"""

from datetime import date, datetime
from pathlib import Path

import pytest
from postgres.models.address_normalization import AddressNormalization
from postgres.models.log_entry import LogEntry
from sqlalchemy import text

# report-gen binds $1, the first day published. SQLAlchemy names it :since.
QUERY = (
    (
        Path(__file__).resolve().parents[3]
        / "tools"
        / "report-gen"
        / "src"
        / "sql"
        / "addresses.sql"
    )
    .read_text()
    .replace("$1", ":since")
)
NOW = datetime(2026, 11, 19)
SINCE = date(2026, 1, 1)
REPORTED = datetime(2026, 6, 1, 12)
MIRACLE_MILE = ("43.6400", "-72.2500")


def add_place(session, normalized: str, coordinates, *raw_spellings: str) -> None:
    lat, lng = coordinates
    for raw in raw_spellings:
        session.add(
            AddressNormalization(
                raw_address=raw,
                normalized_address=normalized,
                lat=float(lat),
                lng=float(lng),
                kind="place",
                source="ai",
                created_at=NOW,
                updated_at=NOW,
            )
        )
    session.flush()


def add_entries(
    session, location: str, *incident_types: str, reported_at: datetime = REPORTED
) -> None:
    for number, incident_type in enumerate(incident_types):
        session.add(
            LogEntry(
                case_number=f"{location}-{incident_type}-{number}-{reported_at:%Y%m%d%H%M}",
                source_url="https://example.com/log.pdf",
                log_date=date(2026, 11, 1),
                reported_at=reported_at,
                location=location,
                incident_type=incident_type,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    session.flush()


def rows(session) -> list[dict]:
    result = session.execute(text(QUERY), {"since": SINCE})
    return [dict(row._mapping) for row in result]


def test_two_spellings_of_one_place_make_one_pin_named_for_the_common_one(
    db_session,
):
    add_place(db_session, "1 Main St", MIRACLE_MILE, "1 MAIN ST", "ONE MAIN STREET")
    add_entries(db_session, "1 MAIN ST", "Alarm", "Alarm", "Alarm")
    add_entries(db_session, "ONE MAIN STREET", "Alarm")

    [pin] = rows(db_session)

    assert pin["raw_address"] == "1 MAIN ST"
    assert (pin["normalized_address"], pin["count"], pin["traffic_count"]) == (
        "1 Main St",
        4,
        0,
    )


def test_road_traffic_is_counted_apart_from_the_place(db_session):
    add_place(db_session, "Lebanon Ford", MIRACLE_MILE, "LEBANON FORD - MIRACLE MILE")
    add_entries(
        db_session,
        "LEBANON FORD - MIRACLE MILE",
        "Alarm",
        "Motor Vehicle Stop",
        "MV Complaint",
        "Assist Motorist",
        "MVA Roadway",
    )

    [pin] = rows(db_session)

    assert (pin["count"], pin["traffic_count"]) == (1, 4)


def test_a_place_with_only_traffic_still_has_a_pin(db_session):
    add_place(db_session, "Route 12A", MIRACLE_MILE, "RT 12A")
    add_entries(db_session, "RT 12A", "Detail Traffic Control", "Road Hazard")

    [pin] = rows(db_session)

    assert (pin["count"], pin["traffic_count"]) == (0, 2)


@pytest.mark.parametrize(
    "incident_type", ["MVA Parking Lot/Private", "Parking in Parking Lot"]
)
def test_a_parking_lot_type_stays_with_the_place(db_session, incident_type):
    add_place(db_session, "Mall", MIRACLE_MILE, "THE MALL")
    add_entries(db_session, "THE MALL", incident_type)

    [pin] = rows(db_session)

    assert (pin["count"], pin["traffic_count"]) == (1, 0)


def test_the_road_traffic_prefix_ignores_case_and_matches_the_start_only(db_session):
    add_place(db_session, "Mall", MIRACLE_MILE, "THE MALL")
    add_entries(
        db_session,
        "THE MALL",
        "MOTOR VEHICLE STOP - ROUTE 12A",
        "motor vehicle stop",
        "Report of Motor Vehicle Stop",
    )

    [pin] = rows(db_session)

    assert (pin["count"], pin["traffic_count"]) == (1, 2)


def test_an_entry_with_no_incident_type_counts_with_the_place(db_session):
    add_place(db_session, "Mall", MIRACLE_MILE, "THE MALL")
    db_session.add(
        LogEntry(
            case_number="no-type",
            source_url="https://example.com/log.pdf",
            log_date=date(2026, 11, 1),
            reported_at=REPORTED,
            location="THE MALL",
            incident_type=None,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    db_session.flush()

    [pin] = rows(db_session)

    assert (pin["count"], pin["traffic_count"]) == (1, 0)


def test_pins_are_sorted_by_count_then_by_traffic_count(db_session):
    add_place(db_session, "Quiet", ("43.61", "-72.21"), "QUIET")
    add_place(db_session, "Busy", ("43.62", "-72.22"), "BUSY")
    add_place(db_session, "Road", ("43.63", "-72.23"), "ROAD")
    add_entries(db_session, "QUIET", "Alarm")
    add_entries(db_session, "BUSY", "Alarm", "Alarm")
    add_entries(db_session, "ROAD", "Motor Vehicle Stop", "Motor Vehicle Stop")

    assert [pin["normalized_address"] for pin in rows(db_session)] == [
        "Busy",
        "Quiet",
        "Road",
    ]


def test_an_entry_before_since_is_left_out_and_one_on_the_day_is_kept(db_session):
    add_place(db_session, "Mall", MIRACLE_MILE, "THE MALL")
    add_entries(
        db_session, "THE MALL", "Alarm", reported_at=datetime(2025, 12, 31, 23, 59)
    )
    add_entries(
        db_session, "THE MALL", "Alarm", "Alarm", reported_at=datetime(2026, 1, 1)
    )

    [pin] = rows(db_session)

    assert pin["count"] == 2


def test_a_place_with_only_entries_before_since_has_no_pin(db_session):
    add_place(db_session, "Old", MIRACLE_MILE, "OLD PLACE")
    add_entries(db_session, "OLD PLACE", "Alarm", reported_at=datetime(2025, 12, 1))

    assert rows(db_session) == []
