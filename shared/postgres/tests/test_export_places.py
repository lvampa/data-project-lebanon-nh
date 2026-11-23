"""The export's places query and call_category, run against the test database.

The query lives in a file that report-gen includes, so this is the same SQL.
"""

import itertools
import json
from datetime import date, datetime
from pathlib import Path

import pytest
from postgres.models.address_normalization import AddressNormalization
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import select, text

# report-gen binds $1, the first day published. SQLAlchemy names it :since.
QUERY = (
    (
        Path(__file__).resolve().parents[3]
        / "tools"
        / "report-gen"
        / "src"
        / "sql"
        / "places.sql"
    )
    .read_text()
    .replace("$1", ":since")
)
NOW = datetime(2026, 11, 19)
SINCE = date(2026, 1, 1)
LOGGED = date(2026, 6, 1)
REPORTED = datetime(2026, 6, 1, 12)
CASE_NUMBERS = itertools.count(1)
MIRACLE_MILE = ("43.6400", "-72.2500")
FORD = "Lebanon Ford, 90 Miracle Mile"


def add_place(
    session,
    normalized: str,
    coordinates,
    *raw_spellings: str,
    kind: str = "address",
    precision: str | None = None,
    street: str | None = None,
) -> None:
    lat, lng = coordinates
    for raw in raw_spellings:
        session.add(
            AddressNormalization(
                raw_address=raw,
                normalized_address=normalized,
                lat=float(lat),
                lng=float(lng),
                kind=kind,
                coordinate_precision=precision,
                street=street,
                source="ai",
                created_at=NOW,
                updated_at=NOW,
            )
        )
    session.flush()


def name_type(session, incident_type: str | None) -> None:
    """Give a raw type the plain name of itself, so the public view shows it as it is."""
    if incident_type is None:
        return
    known = session.scalar(
        select(IncidentTypeCategory.id).where(
            IncidentTypeCategory.raw_incident_type == incident_type
        )
    )
    if known is None:
        session.add(
            IncidentTypeCategory(
                raw_incident_type=incident_type,
                normalized_type=incident_type,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.flush()


def add_entries(
    session,
    location: str,
    *incident_types: str | None,
    log_date: date = LOGGED,
    reported_at: datetime | None = REPORTED,
    disposition: str | None = None,
    call_source: str | None = None,
    plain: bool = True,
) -> None:
    for number, incident_type in enumerate(incident_types):
        if plain:
            name_type(session, incident_type)
        session.add(
            LogEntry(
                case_number=f"26-{next(CASE_NUMBERS):06}",
                source_url=f"https://example.com/{number}.pdf",
                log_date=log_date,
                reported_at=reported_at,
                location=location,
                incident_type=incident_type,
                disposition=disposition,
                call_source=call_source,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    session.flush()


def rows(session) -> list[dict]:
    result = session.execute(text(QUERY), {"since": SINCE})
    return [dict(row._mapping) for row in result]


def card(session, pin_id: str) -> dict:
    [row] = [row for row in rows(session) if row["id"] == pin_id]
    return json.loads(row["card"])


# --- the category of a call ---


@pytest.mark.parametrize(
    ("incident_type", "call_source", "category"),
    [
        ("Motor Vehicle Stop - Warning", None, "traffic"),
        ("mv complaint", None, "traffic"),
        ("Detail Traffic Control", None, "traffic"),
        ("MVA Parking Lot/Private", None, "premises"),
        ("Parking in Parking Lot", None, "premises"),
        ("BUSINESS CHECK - CLOSED", None, "checks"),
        ("Directed Patrol", None, "checks"),
        ("FOOT PATROL", None, "checks"),
        ("FD Alarm Work/Test", None, "alarms"),
        ("Supervisory Alarm", None, "alarms"),
        ("Suspicious Incident", "Alarm System", "alarms"),
        (None, "Alarm System", "alarms"),
        (None, "ALARM SYSTEM", "alarms"),
        ("Paperwork Service Subpoena", None, "admin"),
        ("Fingerprinting", None, "admin"),
        ("Civil Subpoena Served", None, "admin"),
        ("Records Request", None, "admin"),
        ("Welfare Check", None, "premises"),
        (None, None, "premises"),
        # A type is in the first category that matches, in the order traffic, checks,
        # alarms, paperwork.
        ("Motor Vehicle Stop Alarm", None, "traffic"),
        ("Report of Motor Vehicle Stop", None, "premises"),
    ],
)
def test_call_category(db_session, incident_type, call_source, category):
    result = db_session.scalar(
        text("SELECT call_category(:incident_type, :call_source)"),
        {"incident_type": incident_type, "call_source": call_source},
    )

    assert result == category


# --- one pin per place, and who counts what ---


def test_two_spellings_of_one_place_make_one_pin_named_for_the_common_one(
    db_session,
):
    add_place(db_session, "1 Main St", MIRACLE_MILE, "1 MAIN ST", "ONE MAIN")
    add_entries(db_session, "1 MAIN ST", "Alarm", "Alarm", "Alarm")
    add_entries(db_session, "ONE MAIN", "Alarm")

    [pin] = rows(db_session)

    # The pin is spelled the way the public view names it, never the log's text.
    assert pin["raw_address"] == "1 Main St"
    assert (pin["normalized_address"], pin["count"], pin["traffic_count"]) == (
        "1 Main St",
        4,
        0,
    )


def test_a_place_leaves_road_traffic_out_of_its_count(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD - MIRACLE MILE")
    add_entries(
        db_session,
        "LEBANON FORD - MIRACLE MILE",
        "Welfare Check",
        "Motor Vehicle Stop",
        "MV Complaint",
        "Assist Motorist",
        "MVA Roadway",
    )

    [pin] = rows(db_session)

    assert (pin["kind"], pin["count"], pin["traffic_count"]) == ("place", 1, 4)


def test_a_road_counts_every_call_including_traffic(db_session):
    add_place(db_session, "Miracle Mile", MIRACLE_MILE, "MIRACLE MILE")
    add_entries(
        db_session, "MIRACLE MILE", "Motor Vehicle Stop", "Road Hazard", "Alarm"
    )

    [pin] = rows(db_session)

    assert (pin["kind"], pin["count"], pin["traffic_count"]) == ("road", 3, 2)


def test_a_place_with_only_traffic_still_has_a_pin(db_session):
    add_place(db_session, "Shop, Route 12A", MIRACLE_MILE, "RT 12A")
    add_entries(db_session, "RT 12A", "Detail Traffic Control", "Road Hazard")

    [pin] = rows(db_session)

    assert (pin["count"], pin["traffic_count"]) == (0, 2)


@pytest.mark.parametrize(
    "incident_type", ["MVA Parking Lot/Private", "Parking in Parking Lot"]
)
def test_a_parking_lot_type_stays_with_the_place(db_session, incident_type):
    add_place(db_session, "Mall, Miracle Mile", MIRACLE_MILE, "THE MALL")
    add_entries(db_session, "THE MALL", incident_type)

    [pin] = rows(db_session)

    assert (pin["count"], pin["traffic_count"]) == (1, 0)


def test_an_entry_with_no_incident_type_counts_with_the_place(db_session):
    add_place(db_session, "Mall, Miracle Mile", MIRACLE_MILE, "THE MALL")
    add_entries(db_session, "THE MALL", None)

    [pin] = rows(db_session)

    assert (pin["count"], pin["traffic_count"]) == (1, 0)


def test_pins_are_sorted_by_count_then_by_traffic_count(db_session):
    add_place(db_session, "Quiet Shop, Miracle Mile", ("43.61", "-72.21"), "QUIET")
    add_place(db_session, "Busy Shop, Miracle Mile", ("43.62", "-72.22"), "BUSY")
    add_place(db_session, "Road Shop, Miracle Mile", ("43.63", "-72.23"), "ROAD")
    add_entries(db_session, "QUIET", "Alarm")
    add_entries(db_session, "BUSY", "Alarm", "Alarm")
    add_entries(db_session, "ROAD", "Motor Vehicle Stop", "Motor Vehicle Stop")

    assert [pin["normalized_address"] for pin in rows(db_session)] == [
        "Busy Shop, Miracle Mile",
        "Quiet Shop, Miracle Mile",
        "Road Shop, Miracle Mile",
    ]


# --- since ---


def test_an_entry_before_since_is_left_out_and_one_on_the_day_is_kept(db_session):
    add_place(db_session, "Mall, Miracle Mile", MIRACLE_MILE, "THE MALL")
    add_entries(db_session, "THE MALL", "Alarm", log_date=date(2025, 12, 31))
    add_entries(db_session, "THE MALL", "Alarm", "Alarm", log_date=date(2026, 1, 1))

    [pin] = rows(db_session)

    assert pin["count"] == 2


def test_an_entry_with_no_reported_time_counts_by_its_log_date(db_session):
    add_place(db_session, "Mall, Miracle Mile", MIRACLE_MILE, "THE MALL")
    add_entries(db_session, "THE MALL", "Alarm", reported_at=None)

    [pin] = rows(db_session)

    assert pin["count"] == 1


def test_a_place_with_only_entries_before_since_has_no_pin(db_session):
    add_place(db_session, "Old Shop, Miracle Mile", MIRACLE_MILE, "OLD PLACE")
    add_entries(db_session, "OLD PLACE", "Alarm", log_date=date(2025, 12, 1))

    assert rows(db_session) == []


# --- ids ---


def test_an_id_is_a_url_safe_slug_of_the_normalized_address(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    add_entries(db_session, "LEBANON FORD", "Alarm")

    [pin] = rows(db_session)

    assert pin["id"] == "lebanon-ford-90-miracle-mile"
    assert pin["id"] == rows(db_session)[0]["id"]


def test_two_pins_with_one_slug_get_different_ids(db_session):
    add_place(db_session, "12 Main St", ("43.60", "-72.20"), "MAIN A")
    add_place(db_session, "12 Main St", ("43.61", "-72.21"), "MAIN B")
    add_entries(db_session, "MAIN A", "Alarm")
    add_entries(db_session, "MAIN B", "Alarm")

    ids = [pin["id"] for pin in rows(db_session)]

    assert sorted(ids) == ["12-main-st", "12-main-st--2"]


@pytest.mark.parametrize(
    ("normalized", "ai_kind", "kind"),
    [
        ("12 Main St", "address", "place"),
        ("12 Main St", "place", "place"),
        ("Lebanon Ford, Miracle Mile", "place", "place"),
        ("Main St", "address", "road"),
        ("Aldrich Ave", "place", "road"),
        ("Campbell St and N Park St", "intersection", "road"),
        ("I-89", "highway", "road"),
        ("1st St and Main St", "intersection", "road"),
        ("89 North", "highway", "road"),
    ],
)
def test_a_road_is_a_bare_street_an_intersection_or_a_highway(
    db_session, normalized, ai_kind, kind
):
    add_place(db_session, normalized, MIRACLE_MILE, "RAW", kind=ai_kind)
    add_entries(db_session, "RAW", "Alarm")

    [pin] = rows(db_session)

    assert pin["kind"] == kind


def test_one_odd_ai_kind_does_not_turn_a_place_into_a_road(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "FORD A", kind="place")
    add_place(db_session, FORD, MIRACLE_MILE, "FORD B", kind="intersection")
    add_entries(db_session, "FORD A", "Alarm")
    add_entries(db_session, "FORD B", "Alarm")

    [pin] = rows(db_session)

    assert pin["kind"] == "place"


def test_a_natural_slug_ending_in_2_does_not_collide_with_a_suffixed_id(db_session):
    add_place(db_session, "12 Main St", ("43.60", "-72.20"), "MAIN A")
    add_place(db_session, "12 Main St", ("43.61", "-72.21"), "MAIN B")
    add_place(db_session, "12 Main St 2", ("43.62", "-72.22"), "MAIN TWO")
    for raw in ("MAIN A", "MAIN B", "MAIN TWO"):
        add_entries(db_session, raw, "Alarm")

    ids = [pin["id"] for pin in rows(db_session)]

    assert len(set(ids)) == 3
    assert "12-main-st-2" in ids


def test_a_roads_card_counts_outcomes_for_every_call(db_session):
    add_place(db_session, "Miracle Mile", MIRACLE_MILE, "MIRACLE MILE")
    add_entries(
        db_session, "MIRACLE MILE", "Motor Vehicle Stop", disposition="Warning Issued"
    )

    assert card(db_session, "miracle-mile")["outcomes"] == [["Warning Issued", 1]]


def test_an_address_with_no_letters_still_gets_an_id(db_session):
    add_place(db_session, "---, Lebanon", MIRACLE_MILE, "DASHES")
    add_entries(db_session, "DASHES", "Alarm")

    [pin] = rows(db_session)

    assert pin["id"] == "lebanon"


# --- a place's card ---


def test_a_places_card_holds_its_counts_types_outcomes_and_latest_calls(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    add_entries(
        db_session,
        "LEBANON FORD",
        "Welfare Check",
        "Welfare Check",
        "Suspicious Incident",
        disposition="Services Rendered",
    )
    add_entries(
        db_session, "LEBANON FORD", "FD Alarm Work/Test", disposition="False Alarm"
    )
    add_entries(
        db_session,
        "LEBANON FORD",
        "BUSINESS CHECK - CLOSED",
        disposition="Log Information",
    )
    add_entries(db_session, "LEBANON FORD", "Motor Vehicle Stop", "Motor Vehicle Stop")

    result = card(db_session, "lebanon-ford-90-miracle-mile")

    assert result["name"] == FORD
    assert result["kind"] == "place"
    assert (result["lat"], result["lng"]) == (43.64, -72.25)
    assert result["count"] == 5
    assert result["categories"] == {
        "premises": 3,
        "traffic": 2,
        "alarms": 1,
        "checks": 1,
        "admin": 0,
    }
    # Only the calls at the place itself, so no alarm, check or traffic type.
    assert result["types"] == [["Welfare Check", 2], ["Suspicious Incident", 1]]
    # The incidents and the alarms, so the false alarm shows. A business check ending in
    # "Log Information" does not, and neither do the traffic stops.
    assert result["outcomes"] == [["Services Rendered", 3], ["False Alarm", 1]]
    assert len(result["calls"]) == 5
    assert "traffic" not in {call["category"] for call in result["calls"]}


def test_a_call_carries_its_case_times_and_officer(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    add_entries(db_session, "LEBANON FORD", "Welfare Check")
    entry = db_session.query(LogEntry).one()
    entry.dispatched_at = datetime(2026, 6, 1, 12, 2)
    entry.arrived_at = datetime(2026, 6, 1, 12, 9)
    entry.cleared_at = datetime(2026, 6, 1, 12, 40)
    entry.officer = "C. Day"
    db_session.flush()

    [call] = card(db_session, "lebanon-ford-90-miracle-mile")["calls"]

    assert call["case_number"] == entry.case_number
    assert call["dispatched_at"] == "2026-06-01T12:02:00"
    assert call["arrived_at"] == "2026-06-01T12:09:00"
    assert call["cleared_at"] == "2026-06-01T12:40:00"
    assert call["officer"] == "C. Day"


def test_a_call_with_no_times_or_officer_has_nulls(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    add_entries(db_session, "LEBANON FORD", "Welfare Check")

    [call] = card(db_session, "lebanon-ford-90-miracle-mile")["calls"]

    assert call["dispatched_at"] is None
    assert call["arrived_at"] is None
    assert call["cleared_at"] is None
    assert call["officer"] is None


def test_ids_do_not_depend_on_counts(db_session):
    add_place(db_session, "12 Main St", ("43.60", "-72.20"), "MAIN A")
    add_place(db_session, "12 Main St", ("43.61", "-72.21"), "MAIN B")
    add_entries(db_session, "MAIN A", "Alarm")
    add_entries(db_session, "MAIN B", "Alarm")
    before = {pin["id"]: pin["lat"] for pin in rows(db_session)}

    add_entries(
        db_session,
        "MAIN B",
        "Alarm",
        "Alarm",
        "Alarm",
        reported_at=datetime(2026, 7, 1),
    )
    after = {pin["id"]: pin["lat"] for pin in rows(db_session)}

    assert before == after


def test_a_places_card_lists_ten_latest_calls_newest_first(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    for day in range(1, 13):
        add_entries(
            db_session,
            "LEBANON FORD",
            "Welfare Check",
            log_date=date(2026, 3, day),
            reported_at=datetime(2026, 3, day, 9),
        )

    calls = card(db_session, "lebanon-ford-90-miracle-mile")["calls"]

    assert len(calls) == 10
    assert calls[0]["reported_at"] == "2026-03-12T09:00:00"
    assert calls[-1]["reported_at"] == "2026-03-03T09:00:00"
    assert set(calls[0]) == {
        "reported_at",
        "incident_type",
        "disposition",
        "call_source",
        "category",
        "source_url",
        "raw_incident_type",
        "case_number",
        "dispatched_at",
        "arrived_at",
        "cleared_at",
        "officer",
    }


def test_a_roads_card_lists_every_type_and_every_call(db_session):
    add_place(db_session, "Miracle Mile", MIRACLE_MILE, "MIRACLE MILE")
    add_entries(db_session, "MIRACLE MILE", "Motor Vehicle Stop", "Motor Vehicle Stop")
    add_entries(db_session, "MIRACLE MILE", "Road Hazard")

    result = card(db_session, "miracle-mile")

    assert result["kind"] == "road"
    assert result["count"] == 3
    assert result["types"] == [["Motor Vehicle Stop", 2], ["Road Hazard", 1]]
    assert {call["category"] for call in result["calls"]} == {"traffic"}


def test_a_card_with_nothing_to_list_has_empty_lists(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    add_entries(db_session, "LEBANON FORD", "Motor Vehicle Stop")

    result = card(db_session, "lebanon-ford-90-miracle-mile")

    assert (result["types"], result["outcomes"], result["calls"]) == ([], [], [])


# --- places that have no spot of their own ---

QUARRY = "Quarry Hill Town Houses, Mount Support Rd"
ROAD_POINT = ("43.6740", "-72.2656")


def add_hanging_place(session, normalized: str = QUARRY, raw: str = "QUARRY") -> None:
    add_place(
        session,
        normalized,
        ROAD_POINT,
        raw,
        kind="place",
        precision="approximate",
        street="MOUNT SUPPORT RD",
    )
    add_entries(session, raw, "Alarm", "Welfare Check")


def add_street(
    session,
    normalized: str = "Mount Support Rd",
    calls: int = 5,
    raw: str = "MT SUPPORT",
) -> None:
    add_place(
        session,
        normalized,
        ("43.6741", "-72.2657"),
        raw,
        kind="place",
        precision="approximate",
        street="MOUNT SUPPORT RD",
    )
    add_entries(session, raw, *["Alarm"] * calls)


def pin(session, normalized: str) -> dict:
    [found] = [p for p in rows(session) if p["normalized_address"] == normalized]
    return found


def test_an_exact_place_is_not_hidden(db_session):
    add_place(
        db_session,
        FORD,
        MIRACLE_MILE,
        "LEBANON FORD",
        precision="exact",
        street="MIRACLE MILE",
    )
    add_entries(db_session, "LEBANON FORD", "Alarm")

    found = pin(db_session, FORD)

    assert (found["precision"], found["street_id"], found["hidden"]) == (
        "exact",
        None,
        False,
    )


def test_a_place_with_no_precision_is_exact(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    add_entries(db_session, "LEBANON FORD", "Alarm")

    assert pin(db_session, FORD)["precision"] == "exact"


def test_an_approximate_place_hangs_on_its_streets_pin_and_keeps_its_count(db_session):
    add_street(db_session)
    add_hanging_place(db_session)

    found = pin(db_session, QUARRY)

    assert (found["precision"], found["street_id"], found["hidden"]) == (
        "approximate",
        "mount-support-rd",
        True,
    )
    assert found["count"] == 2
    assert pin(db_session, "Mount Support Rd")["hidden"] is False


def test_an_approximate_place_with_no_street_pin_keeps_its_pin(db_session):
    add_hanging_place(db_session)

    found = pin(db_session, QUARRY)

    assert (found["precision"], found["street_id"], found["hidden"]) == (
        "approximate",
        None,
        False,
    )


def test_an_approximate_place_with_no_street_is_not_hidden(db_session):
    add_street(db_session)
    add_place(
        db_session, QUARRY, ROAD_POINT, "QUARRY", kind="place", precision="approximate"
    )
    add_entries(db_session, "QUARRY", "Alarm")

    assert pin(db_session, QUARRY)["hidden"] is False


def test_an_intersection_with_the_same_first_street_is_not_the_streets_pin(db_session):
    add_place(
        db_session,
        "Mount Support Rd and Dartmouth Ave",
        ("43.6742", "-72.2650"),
        "CROSS",
        kind="intersection",
        precision="approximate",
        street="MOUNT SUPPORT RD",
    )
    add_entries(db_session, "CROSS", *["Alarm"] * 9)
    add_street(db_session, calls=2)
    add_hanging_place(db_session)

    assert pin(db_session, QUARRY)["street_id"] == "mount-support-rd"


def test_an_approximate_road_or_intersection_keeps_its_pin(db_session):
    add_street(db_session)
    add_place(
        db_session,
        "Mount Support Rd and Dartmouth Ave",
        ("43.6742", "-72.2650"),
        "CROSS",
        kind="intersection",
        precision="approximate",
        street="MOUNT SUPPORT RD",
    )
    add_entries(db_session, "CROSS", "Alarm")

    assert [p["hidden"] for p in rows(db_session)] == [False, False]


def test_the_busiest_street_pin_wins_and_a_tie_goes_to_the_lowest_id(db_session):
    add_street(db_session, "Mount Support Rd", 5, "MT SUPPORT")
    add_place(
        db_session,
        "Mount Support Road",
        ("43.6750", "-72.2660"),
        "MT SUPPORT ROAD",
        kind="place",
        precision="approximate",
        street="MOUNT SUPPORT RD",
    )
    add_entries(db_session, "MT SUPPORT ROAD", *["Alarm"] * 5)
    add_hanging_place(db_session)

    assert pin(db_session, QUARRY)["street_id"] == "mount-support-rd"

    add_entries(
        db_session,
        "MT SUPPORT ROAD",
        "Alarm",
        log_date=LOGGED,
        reported_at=datetime(2026, 7, 1),
    )

    assert pin(db_session, QUARRY)["street_id"] == "mount-support-road"


def test_a_place_is_approximate_when_any_of_its_spellings_is(db_session):
    add_place(
        db_session,
        QUARRY,
        ROAD_POINT,
        "QUARRY A",
        kind="place",
        street="MOUNT SUPPORT RD",
    )
    add_place(
        db_session,
        QUARRY,
        ROAD_POINT,
        "QUARRY B",
        kind="place",
        precision="approximate",
        street="MOUNT SUPPORT RD",
    )
    add_entries(db_session, "QUARRY A", "Alarm")
    add_entries(db_session, "QUARRY B", "Alarm")

    assert pin(db_session, QUARRY)["precision"] == "approximate"


# --- every entry of a pin, for activity.json ---


def entries(session, normalized: str) -> list[list]:
    return json.loads(pin(session, normalized)["entries"])


def test_a_place_lists_every_entry_including_the_road_traffic_its_count_leaves_out(
    db_session,
):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    add_entries(db_session, "LEBANON FORD", "Welfare Check", "Motor Vehicle Stop")

    listed = entries(db_session, FORD)

    assert pin(db_session, FORD)["count"] == 1
    assert sorted(entry[1] for entry in listed) == ["premises", "traffic"]


def test_an_entry_carries_its_time_kind_type_outcome_source_officer_and_times(
    db_session,
):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    add_entries(
        db_session,
        "LEBANON FORD",
        "Welfare Check",
        disposition="Investigated",
        call_source="Telephone",
    )
    entry = db_session.query(LogEntry).one()
    entry.dispatched_at = datetime(2026, 6, 1, 12, 2)
    entry.arrived_at = datetime(2026, 6, 1, 12, 9)
    entry.cleared_at = datetime(2026, 6, 1, 12, 40)
    entry.officer = "C. Day"
    db_session.flush()

    assert entries(db_session, FORD) == [
        [
            "2026-06-01T12:00:00",
            "premises",
            "Welfare Check",
            "Investigated",
            "Telephone",
            "C. Day",
            "2026-06-01T12:02:00",
            "2026-06-01T12:09:00",
            "2026-06-01T12:40:00",
        ]
    ]


def test_entries_are_in_log_order(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    add_entries(db_session, "LEBANON FORD", "Late", reported_at=datetime(2026, 6, 2, 9))
    add_entries(
        db_session, "LEBANON FORD", "Early", reported_at=datetime(2026, 6, 1, 9)
    )

    assert [entry[2] for entry in entries(db_session, FORD)] == ["Early", "Late"]


def test_an_entry_with_no_reported_time_is_placed_at_its_log_day(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD")
    add_entries(db_session, "LEBANON FORD", "Welfare Check", reported_at=None)

    [entry] = entries(db_session, FORD)

    assert entry[0] == "2026-06-01T00:00:00"


def test_a_hidden_place_keeps_its_own_entries_and_its_street_keeps_its_own(db_session):
    add_street(db_session)
    add_hanging_place(db_session)

    assert pin(db_session, QUARRY)["hidden"] is True
    assert len(entries(db_session, QUARRY)) == 2
    assert len(entries(db_session, "Mount Support Rd")) == 5


def test_every_published_entry_is_on_exactly_one_pin(db_session):
    add_place(db_session, FORD, MIRACLE_MILE, "LEBANON FORD", "LEBANON FORD INC")
    add_street(db_session)
    add_hanging_place(db_session)
    add_entries(db_session, "LEBANON FORD", "Welfare Check", "Motor Vehicle Stop")
    add_entries(db_session, "LEBANON FORD INC", "Alarm")
    add_entries(db_session, "LEBANON FORD", "Too early", log_date=date(2025, 12, 31))

    listed = sum(len(json.loads(row["entries"])) for row in rows(db_session))

    published = db_session.scalar(
        text("SELECT count(*) FROM log_entries WHERE log_date >= :since"),
        {"since": SINCE},
    )
    assert listed == published == 10


# --- the public rules: a flagged location, and plain type names ---

PERSON = "F and 2 Yo Child, Example St"
STREET_POINT = ("43.6741", "-72.2657")


def add_bare_street(session, calls: int = 3, raw: str = "EX ST") -> None:
    add_place(
        session,
        "Example St",
        STREET_POINT,
        raw,
        kind="place",
        precision="exact",
        street="EXAMPLE ST",
    )
    add_entries(session, raw, *["Welfare Check"] * calls)


def add_flagged(session, raw: str = "F AND 2 YO CHILD", calls: int = 2) -> None:
    add_place(
        session,
        PERSON,
        ("43.6740", "-72.2650"),
        raw,
        kind="place",
        precision="exact",
        street="EXAMPLE ST",
    )
    session.execute(
        text(
            "UPDATE address_normalizations SET names_person = true WHERE raw_address = :r"
        ),
        {"r": raw},
    )
    add_entries(session, raw, *["Alarm"] * calls)


def everything_published(session) -> str:
    """All the text the places query hands to the export, as one string."""
    return json.dumps([{k: str(v) for k, v in row.items()} for row in rows(session)])


def test_a_flagged_locations_calls_count_on_its_streets_pin(db_session):
    add_bare_street(db_session, calls=3)
    add_flagged(db_session, calls=2)

    found = pin(db_session, "Example St")

    assert found["count"] == 5
    assert len(rows(db_session)) == 1


def test_a_flagged_location_has_no_pin_and_no_name_of_its_own(db_session):
    add_bare_street(db_session)
    add_flagged(db_session)

    published = everything_published(db_session)

    assert "Child" not in published and "CHILD" not in published
    assert "F and 2 Yo" not in published
    assert [p["normalized_address"] for p in rows(db_session)] == ["Example St"]


def test_a_flagged_locations_calls_are_in_its_streets_card_and_activity(db_session):
    add_bare_street(db_session, calls=1)
    add_flagged(db_session, calls=2)

    [found] = rows(db_session)

    assert json.loads(found["card"])["categories"]["alarms"] == 2
    assert len(json.loads(found["entries"])) == found["count"] == 3


def test_a_flagged_location_whose_street_has_no_pin_is_off_the_map(db_session):
    add_flagged(db_session)

    assert rows(db_session) == []


def test_a_flagged_location_with_no_street_is_off_the_map(db_session):
    add_bare_street(db_session)
    add_place(
        db_session,
        PERSON,
        ("43.6740", "-72.2650"),
        "NO STREET",
        kind="place",
        street=None,
    )
    db_session.execute(
        text(
            "UPDATE address_normalizations SET names_person = true WHERE raw_address = 'NO STREET'"
        )
    )
    add_entries(db_session, "NO STREET", "Alarm")

    assert pin(db_session, "Example St")["count"] == 3


def test_a_human_row_publishes_only_its_street(db_session):
    add_bare_street(db_session)
    add_place(
        db_session,
        "Hand Placed Shop, Example St",
        ("43.6745", "-72.2640"),
        "HAND",
        kind="place",
        precision="exact",
        street="EXAMPLE ST",
    )
    db_session.execute(
        text(
            "UPDATE address_normalizations SET source = 'human' WHERE raw_address = 'HAND'"
        )
    )
    add_entries(db_session, "HAND", "Alarm")

    assert [p["normalized_address"] for p in rows(db_session)] == ["Example St"]
    assert "Hand Placed" not in everything_published(db_session)


def test_a_flagged_location_hangs_on_the_busiest_bare_street_pin(db_session):
    add_bare_street(db_session, calls=2, raw="EX ST")
    add_place(
        db_session,
        "Example Road",
        ("43.6750", "-72.2660"),
        "MT SUPPORT ROAD",
        kind="place",
        precision="exact",
        street="EXAMPLE ST",
    )
    add_entries(db_session, "MT SUPPORT ROAD", *["Welfare Check"] * 4)
    add_flagged(db_session, calls=1)

    assert pin(db_session, "Example Road")["count"] == 5
    assert pin(db_session, "Example St")["count"] == 2


def test_an_intersection_is_never_the_pin_a_flagged_location_hangs_on(db_session):
    add_place(
        db_session,
        "Example St and Sample Ave",
        ("43.6742", "-72.2650"),
        "CROSS",
        kind="intersection",
        precision="exact",
        street="EXAMPLE ST",
    )
    add_entries(db_session, "CROSS", *["Alarm"] * 9)
    add_flagged(db_session)

    assert [p["count"] for p in rows(db_session)] == [9]


def test_a_type_with_no_plain_name_is_other_and_keeps_its_category(db_session):
    add_bare_street(db_session, calls=0)
    add_entries(
        db_session,
        "EX ST",
        "DEP INFO - DOE",
        "Motor Vehicle Stop - DOE",
        plain=False,
    )

    [found] = rows(db_session)
    result = json.loads(found["card"])

    # The category comes from the log's own type, so a traffic stop stays traffic.
    assert result["categories"]["traffic"] == 1
    assert result["categories"]["premises"] == 1
    assert result["types"] == []
    assert "DOE" not in json.dumps(json.loads(found["entries"]))
    assert [e[2] for e in json.loads(found["entries"])] == ["Other", "Other"]


def test_the_cards_calls_carry_the_logs_own_type_for_the_details(db_session):
    add_bare_street(db_session, calls=0)
    add_type_name(db_session, "80 YOM CPR", "Cardiac arrest")
    add_entries(db_session, "EX ST", "80 YOM CPR", plain=False)

    [found] = rows(db_session)
    [call] = json.loads(found["card"])["calls"]

    assert (call["incident_type"], call["raw_incident_type"]) == (
        "Cardiac arrest",
        "80 YOM CPR",
    )
    assert json.loads(found["card"])["types"] == [["Cardiac arrest", 1]]


def add_type_name(session, raw: str, normalized: str) -> None:
    session.add(
        IncidentTypeCategory(
            raw_incident_type=raw,
            normalized_type=normalized,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.flush()


def test_every_pins_count_matches_its_activity_entries(db_session):
    add_bare_street(db_session)
    add_flagged(db_session)
    add_place(
        db_session, FORD, MIRACLE_MILE, "LEBANON FORD", kind="place", precision="exact"
    )
    add_entries(db_session, "LEBANON FORD", "Alarm", "Motor Vehicle Stop")

    for found in rows(db_session):
        entries = json.loads(found["entries"])
        counted = [e for e in entries if e[1] != "traffic" or found["kind"] == "road"]
        assert len(counted) == found["count"], found["id"]
