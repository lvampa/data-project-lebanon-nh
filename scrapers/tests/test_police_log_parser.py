from datetime import datetime
from pathlib import Path
from typing import Any

import pypdf
import pytest
from parsers.police_log import (
    EXTRACTOR_VERSION,
    PARSER_VERSION,
    count_header_lines,
    parse_log_entries,
)

# Entries cut from the city's real daily logs for 2026-11-01, 11-05 and 11-08, with
# every officer name and code replaced by a placeholder.
FIXTURES = Path(__file__).parent / "fixtures" / "police_log"

# "Vicinity of:" did not appear in those logs, so its tests build the line by hand.
HEADER = (
    "For Date: 05/11/2026  -  Monday\nCall   Number   Time   Call   Reason   Action\n"
)


def fixture_text(log_date: str) -> str:
    return (FIXTURES / f"{log_date}.txt").read_text()


def entries_by_case(log_date: str) -> dict[str, dict[str, Any]]:
    entries = parse_log_entries(fixture_text(log_date))
    return {entry["case_number"]: entry for entry in entries}


def parse_one(entry_text: str) -> dict[str, Any]:
    [entry] = parse_log_entries(HEADER + entry_text)
    return entry


@pytest.fixture(scope="module")
def nov_1() -> dict[str, dict[str, Any]]:
    return entries_by_case("2026-11-01")


@pytest.fixture(scope="module")
def nov_5() -> dict[str, dict[str, Any]]:
    return entries_by_case("2026-11-05")


def test_parser_version_is_3_and_the_extractor_version_is_pypdfs():
    assert PARSER_VERSION == 3
    assert pypdf.__version__ == EXTRACTOR_VERSION


# --- whole logs ---


@pytest.mark.parametrize(
    ("log_date", "count"), [("2026-11-01", 14), ("2026-11-05", 3), ("2026-11-08", 1)]
)
def test_every_entry_in_a_log_parses_with_a_known_disposition(log_date, count):
    text = fixture_text(log_date)

    entries = parse_log_entries(text)

    assert len(entries) == count == count_header_lines(text)
    assert not any(entry["parse_error"] for entry in entries)
    assert not any(entry["disposition_unmatched"] for entry in entries)


def test_a_log_with_no_entries_or_no_date_parses_to_nothing():
    assert parse_log_entries("") == []
    assert parse_log_entries("26-13339        0106 Phone - Something Log") == []


# --- the header line ---


def test_header_fields(nov_1):
    entry = nov_1["26-31404"]

    assert entry["call_source"] == "Initiated"
    assert entry["incident_type"] == "Motor Vehicle Stop"
    assert entry["disposition"] == "Warning Issued"
    assert entry["reported_at"] == datetime(2026, 11, 1, 0, 42)


def test_a_header_followed_by_a_blank_line_still_parses(nov_1):
    entry = nov_1["26-31439"]

    assert entry["call_source"] == "Cellular"
    assert entry["location"] == "ROUTE 120 + CENTERRA PKWY"


def test_call_source_comes_from_the_call_source_line():
    entry = parse_one(
        "26-20003        1015 Phone - Suspicious Person Advised\n"
        "       Call Source:    Walk-In\n"
    )

    assert entry["call_source"] == "Walk-In"


def test_call_source_falls_back_to_the_header_when_there_is_no_line():
    entry = parse_one("26-20004        1015 Phone - Suspicious Person Advised\n")

    assert entry["call_source"] == "Phone"


# --- dispositions ---


def test_taken_referred_to_other_agency_is_a_disposition(nov_1):
    entry = nov_1["26-31439"]

    assert entry["incident_type"] == "MV Complaint"
    assert entry["disposition"] == "Taken/Referred to Other Agency"


def test_a_disposition_typed_in_capitals_is_split_off_in_the_listed_spelling(nov_1):
    entry = nov_1["26-31454"]

    assert entry["incident_type"] == "Property Returned"
    assert entry["disposition"] == "Property Returned"
    assert entry["disposition_unmatched"] is False


def test_a_type_that_is_also_a_disposition_keeps_its_real_ending(nov_1):
    entry = nov_1["26-31412"]

    assert entry["incident_type"] == "Property Returned"
    assert entry["disposition"] == "Investigated"


@pytest.mark.parametrize(
    ("reason_action", "incident_type", "disposition"),
    [
        ("Welfare Check Investigated", "Welfare Check", "Investigated"),
        ("Theft Summons Issued", "Theft", "Summons Issued"),
        ("Road Debris Removed Hazard", "Road Debris", "Removed Hazard"),
        ("Medical Aid Transported/Relayed", "Medical Aid", "Transported/Relayed"),
        ("Civil Matter Paperwork Served", "Civil Matter", "Paperwork Served"),
        (
            "Civil Matter Paperwork NOT Served",
            "Civil Matter",
            "Paperwork NOT Served",
        ),
    ],
)
def test_dispositions_found_in_the_stored_pdfs_are_split_off(
    reason_action, incident_type, disposition
):
    entry = parse_one(f"26-20011        1015 Phone - {reason_action}\n")

    assert entry["incident_type"] == incident_type
    assert entry["disposition"] == disposition
    assert entry["disposition_unmatched"] is False


def test_an_unknown_disposition_keeps_the_unsplit_text_and_is_marked():
    entry = parse_one("26-20012        1015 Phone - Suspicious Person Frobnicated\n")

    assert entry["incident_type"] == "Suspicious Person Frobnicated"
    assert entry["disposition"] is None
    assert entry["disposition_unmatched"] is True


# --- officer ---


def test_the_officer_code_and_name_are_kept_apart(nov_1):
    entry = nov_1["26-31404"]

    assert entry["officer_code"] == "XA"
    assert entry["officer"] == "A. Example"


@pytest.mark.parametrize(
    ("case_number", "name"),
    [("26-31428", "D. Example"), ("26-31439", "F. Example")],
)
def test_a_corporal_or_sergeant_rank_is_not_part_of_the_name(nov_1, case_number, name):
    assert nov_1[case_number]["officer"] == name


def test_an_entry_with_no_primary_id_has_no_officer(nov_1):
    entry = nov_1["26-31423"]

    assert entry["officer"] is None
    assert entry["officer_code"] is None


# --- location ---


def test_a_place_code_is_kept_apart_from_the_location(nov_1):
    entry = nov_1["26-31407"]

    assert entry["place_code"] == "L 2W"
    assert entry["location"] == "WHIPPLE BLOCK - WEST PARK ST"


def test_an_intersection_written_with_a_plus_is_kept_as_printed(nov_1):
    entry = nov_1["26-31404"]

    assert entry["place_code"] is None
    assert entry["location"] == "ROUTE 120 + CENTERRA PKWY"


def test_a_location_after_a_page_break_is_found(nov_1):
    entry = nov_1["26-31459"]

    assert entry["place_code"] == "L 36"
    assert entry["location"] == "LEBANON POLICE DEPARTMENT - POVERTY LN"
    assert "Page:" not in entry["raw_text"]


def test_location_comes_from_a_vicinity_of_line():
    entry = parse_one(
        "26-20001        1015 Phone - Disabled Motor Vehicle Assisted Party\n"
        "       Call Source:    Telephone\n"
        "      Vicinity of:    I-89 NB MM 18\n"
    )

    assert entry["location"] == "I-89 NB MM 18"


def test_a_location_line_wins_over_a_vicinity_line():
    entry = parse_one(
        "26-20002        1015 Phone - Disabled Motor Vehicle Assisted Party\n"
        "  Location/Address:    MAIN ST\n"
        "      Vicinity of:    I-89 NB MM 18\n"
    )

    assert entry["location"] == "MAIN ST"


# --- references ---


def test_refer_to_kinds_from_the_real_logs(nov_1, nov_5):
    assert nov_1["26-31436"]["refer_to"] == [
        {"kind": "Incident", "number": "26L-1035-OF"}
    ]
    assert nov_1["26-31456"]["refer_to"] == [
        {"kind": "Accident", "number": "26L-340-AC"}
    ]
    assert nov_5["26-31819"]["refer_to"] == [
        {"kind": "Summons", "number": "26L-975-AR"}
    ]
    assert nov_5["26-31850"]["refer_to"] == [{"kind": "Citation", "number": "26-31850"}]
    assert nov_5["26-31868"]["refer_to"] == [{"kind": "Arrest", "number": "26L-977-AR"}]
    assert nov_5["26-31868"]["reference_number"] == "26L-977-AR"


def test_refer_to_is_none_when_the_entry_has_no_reference(nov_1):
    assert nov_1["26-31404"]["refer_to"] is None
    assert nov_1["26-31404"]["reference_number"] is None


def test_every_refer_to_kind_is_kept_in_order():
    entry = parse_one(
        "26-20009        1015 Phone - Motor Vehicle Crash Report Taken\n"
        "       Refer To Incident:      26L-426-OF\n"
        "       Refer To Citation:      26L-77-CT\n"
        "       Refer To Accident:      26L-12-AC\n"
        "       Refer To Arrest:        26L-346-AR\n"
    )

    assert [ref["kind"] for ref in entry["refer_to"]] == [
        "Incident",
        "Citation",
        "Accident",
        "Arrest",
    ]
    assert entry["reference_number"] == "26L-426-OF"


# --- dispatch times ---


def test_all_four_times_and_both_durations(nov_1):
    entry = nov_1["26-31413"]

    assert entry["dispatched_at"] == datetime(2026, 11, 1, 7, 44, 25)
    assert entry["enroute_at"] == datetime(2026, 11, 1, 7, 47, 0)
    assert entry["arrived_at"] == datetime(2026, 11, 1, 7, 56, 57)
    assert entry["cleared_at"] == datetime(2026, 11, 1, 7, 58, 57)
    assert entry["response_seconds"] == 752
    assert entry["scene_seconds"] == 120


def test_times_come_from_the_primary_units_block_not_the_first(nov_1):
    # The first unit listed (XC) is a backup; the primary is XB.
    entry = nov_1["26-31412"]

    assert entry["officer_code"] == "XB"
    assert entry["dispatched_at"] == datetime(2026, 11, 1, 7, 34, 48)
    assert entry["enroute_at"] == datetime(2026, 11, 1, 7, 34, 51)
    assert entry["arrived_at"] == datetime(2026, 11, 1, 7, 34, 52)
    assert entry["cleared_at"] == datetime(2026, 11, 1, 7, 44, 18)
    assert entry["response_seconds"] == 4


def test_a_primary_unit_with_no_dispatch_does_not_borrow_a_backups(nov_1):
    # The primary (XD) printed only Arvd and Clrd; the backup (XB) has a Disp.
    entry = nov_1["26-31428"]

    assert entry["dispatched_at"] is None
    assert entry["arrived_at"] == datetime(2026, 11, 1, 11, 4, 0)


def test_times_fall_back_to_the_first_block_when_the_primary_has_none():
    entry = parse_one(
        "26-20013        1015 Phone - Suspicious Person Advised\n"
        "        Primary Id:    XZ - Officer Z. Example\n"
        "                ID:    XA -   \n"
        "                       Disp-10:16:00  Arvd-10:20:00  Clrd-10:30:00\n"
    )

    assert entry["dispatched_at"] == datetime(2026, 5, 11, 10, 16, 0)


def test_an_entry_with_no_dispatch_time_still_gets_arrived_and_cleared(nov_1):
    entry = nov_1["26-31404"]

    assert entry["dispatched_at"] is None
    assert entry["arrived_at"] == datetime(2026, 11, 1, 0, 42, 0)
    assert entry["cleared_at"] == datetime(2026, 11, 1, 0, 50, 9)
    assert entry["response_seconds"] is None
    assert entry["scene_seconds"] == 489


def test_a_clear_time_after_midnight_carries_its_own_date(nov_1):
    entry = nov_1["26-31441"]

    assert entry["arrived_at"] == datetime(2026, 11, 1, 15, 49, 0)
    assert entry["cleared_at"] == datetime(2026, 11, 2, 0, 0, 6)
    assert entry["scene_seconds"] == 29466


def test_every_time_on_a_line_may_carry_its_own_date():
    entry = parse_one(
        "26-20014        2350 Phone - Suspicious Person Advised\n"
        "                ID:    XA -   \n"
        "                       Disp-23:51:00  Enrt-11/12/2026 @ 00:01:00  "
        "Arvd-11/12/2026 @ 00:05:00  Clrd-11/12/2026 @ 00:20:00\n"
    )

    assert entry["dispatched_at"] == datetime(2026, 5, 11, 23, 51, 0)
    assert entry["enroute_at"] == datetime(2026, 11, 12, 0, 1, 0)
    assert entry["arrived_at"] == datetime(2026, 11, 12, 0, 5, 0)
    assert entry["cleared_at"] == datetime(2026, 11, 12, 0, 20, 0)


def test_an_undated_dispatch_after_midnight_lands_on_the_next_day():
    # Reported at 23:14, dispatched at 00:49: the line carries no date.
    entry = parse_one(
        "26-20015        2314 Phone - Suspicious Person Advised\n"
        "        Primary Id:    XH - Officer H. Example\n"
        "                ID:    XH -   \n"
        "                       Disp-00:49:00  Enrt-00:50:00  Arvd-00:55:00  "
        "Clrd-01:10:00\n"
    )

    assert entry["dispatched_at"] == datetime(2026, 5, 12, 0, 49, 0)
    assert entry["enroute_at"] == datetime(2026, 5, 12, 0, 50, 0)
    assert entry["arrived_at"] == datetime(2026, 5, 12, 0, 55, 0)
    assert entry["cleared_at"] == datetime(2026, 5, 12, 1, 10, 0)
    assert entry["response_seconds"] == 360
    assert entry["scene_seconds"] == 900


def test_an_undated_arrival_after_midnight_with_no_dispatch_lands_on_the_next_day():
    entry = parse_one(
        "26-20016        2358 Initiated - Directed Patrol Log Information\n"
        "                ID:    XA -   \n"
        "                       Arvd-00:02:00  Clrd-00:10:00\n"
    )

    assert entry["arrived_at"] == datetime(2026, 5, 12, 0, 2, 0)
    assert entry["cleared_at"] == datetime(2026, 5, 12, 0, 10, 0)


def test_an_arrival_a_minute_before_the_reported_time_stays_on_the_same_day():
    # The call is logged after the officer is already there.
    entry = parse_one(
        "26-20018        1015 Initiated - Directed Patrol Log Information\n"
        "                ID:    XA -   \n"
        "                       Arvd-10:14:00  Clrd-10:30:00\n"
    )

    assert entry["arrived_at"] == datetime(2026, 5, 11, 10, 14, 0)
    assert entry["cleared_at"] == datetime(2026, 5, 11, 10, 30, 0)
    assert entry["scene_seconds"] == 960


def test_a_same_day_dispatch_line_keeps_the_log_date():
    entry = parse_one(
        "26-20017        1015 Phone - Suspicious Person Advised\n"
        "                ID:    XA -   \n"
        "                       Disp-10:16:00  Enrt-10:17:00  Arvd-10:20:00  "
        "Clrd-10:30:00\n"
    )

    assert entry["dispatched_at"] == datetime(2026, 5, 11, 10, 16, 0)
    assert entry["cleared_at"] == datetime(2026, 5, 11, 10, 30, 0)


def test_a_dispatch_with_no_arrival_and_a_clear_after_midnight(nov_1):
    entry = nov_1["26-31459"]

    assert entry["dispatched_at"] == datetime(2026, 11, 1, 22, 29, 42)
    assert entry["arrived_at"] is None
    assert entry["cleared_at"] == datetime(2026, 11, 2, 0, 31, 52)


def test_an_entry_split_by_a_page_break_keeps_its_times(nov_1):
    entry = nov_1["26-31424"]

    assert entry["location"] == "EASTMAN HILL"
    assert entry["dispatched_at"] == datetime(2026, 11, 1, 10, 36, 36)


def test_an_entry_with_no_dispatch_line_has_no_times(nov_1):
    entry = nov_1["26-31423"]

    assert entry["dispatched_at"] is None
    assert entry["response_seconds"] is None


def test_raw_text_is_the_entry_block_alone(nov_1):
    raw_text = nov_1["26-31404"]["raw_text"]

    assert raw_text.startswith("26-31404")
    assert "26-31407" not in raw_text
