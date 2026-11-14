from datetime import datetime

import pypdf
import pytest
from parsers.police_log import (
    EXTRACTOR_VERSION,
    PARSER_VERSION,
    parse_log_entries,
)

# Reflects the real Lebanon NH dispatch log PDF format
SAMPLE_TEXT = """\
 Lebanon Police Department Page:   1
  Dispatch Log  From: 05/01/2026  Thru: 05/01/2026     0000 - 2359    Printed: 05/04/2026
For Date: 05/01/2026  -  Friday
Call   Number   Time   Call   Reason   Action
26-13339        0106 Phone - Telephone Harassment Incident Report Taken
       Call Source:    Telephone
        Primary Id:    SMN - Officer Stephan Nix
  Location/Address:    [L TWD4] TIMBERWOOD COMMONS - TIMBERWOOD DR
                ID:    SMN -
                       Disp-01:07:39  Enrt-01:39:04  Arvd-02:05:44  Clrd-02:41:21
       Refer To Incident:      26L-426-OF
26-13343        0640 Phone - BOL/ATL Broadcast Log Information
       Call Source:    Telephone
  Location/Address:    [L 36] FROM THETFORD - POVERTY LN
                ID:    BOL1 -
                       Disp-06:54:31                 Arvd-06:55:08  Clrd-09:04:39
26-13344        0645 Phone - Suspicious Motor Vehicle Gone on Arrival
       Call Source:    Telephone
        Primary Id:    FLF - Officer Felicia L Figol
  Location/Address:    EAGLE RIDGE RD
                ID:    FLF -
                       Disp-06:50:53  Enrt-06:51:04  Arvd-06:59:30  Clrd-07:03:29
"""

# Entry that spans a page break — page header injected between entry header and its sub-fields
SAMPLE_PAGE_BREAK = """\
For Date: 05/01/2026  -  Friday
Call   Number   Time   Call   Reason   Action
26-13351        0827 Phone - FD Alarm Work/Test Log Information
 Lebanon Police Department Page:   2
  Dispatch Log  From: 05/01/2026  Thru: 05/01/2026     0000 - 2359    Printed: 05/04/2026
       Call Source:    Telephone
  Location/Address:    [L BESTB] BEST BUY - PLAINFIELD RD
"""


def test_parses_three_entries():
    entries = parse_log_entries(SAMPLE_TEXT)
    assert len(entries) == 3


def test_first_entry_fields():
    entries = parse_log_entries(SAMPLE_TEXT)
    e = entries[0]
    assert e["case_number"] == "26-13339"
    assert e["call_source"] == "Telephone"
    assert e["incident_type"] == "Telephone Harassment"
    assert e["disposition"] == "Incident Report Taken"
    assert e["officer"] == "Stephan Nix"
    assert e["location"] == "TIMBERWOOD COMMONS - TIMBERWOOD DR"
    assert e["reference_number"] == "26L-426-OF"
    assert e["parse_error"] is False


def test_reported_at_is_datetime_with_correct_time():
    entries = parse_log_entries(SAMPLE_TEXT)
    e = entries[0]
    assert isinstance(e["reported_at"], datetime)
    assert e["reported_at"] == datetime(2026, 5, 1, 1, 6)


def test_entry_without_officer_has_none():
    entries = parse_log_entries(SAMPLE_TEXT)
    e = entries[1]  # 26-13343 has no Primary Id and no Refer To
    assert e["officer"] is None
    assert e["reference_number"] is None
    assert e["case_number"] == "26-13343"


def test_broadcast_log_disposition():
    entries = parse_log_entries(SAMPLE_TEXT)
    e = entries[1]
    assert e["disposition"] == "Broadcast Log Information"
    assert e["incident_type"] == "BOL/ATL"


def test_location_strips_bracket_code():
    entries = parse_log_entries(SAMPLE_TEXT)
    assert entries[0]["location"] == "TIMBERWOOD COMMONS - TIMBERWOOD DR"
    assert entries[1]["location"] == "FROM THETFORD - POVERTY LN"
    assert entries[2]["location"] == "EAGLE RIDGE RD"


def test_page_break_entry_parsed_correctly():
    entries = parse_log_entries(SAMPLE_PAGE_BREAK)
    assert len(entries) == 1
    e = entries[0]
    assert e["case_number"] == "26-13351"
    assert e["call_source"] == "Telephone"
    assert e["incident_type"] == "FD Alarm Work/Test"
    assert e["disposition"] == "Log Information"
    assert e["location"] == "BEST BUY - PLAINFIELD RD"


def test_entry_raw_text_contains_entry_block():
    entries = parse_log_entries(SAMPLE_TEXT)
    # raw_text should be the entry block, not the full PDF text
    assert "26-13339" in entries[0]["raw_text"]
    assert entries[0]["raw_text"].startswith("26-13339")
    # should not bleed into the next entry
    assert "26-13343" not in entries[0]["raw_text"]


def test_empty_text_returns_empty_list():
    assert parse_log_entries("") == []


def test_no_date_header_returns_empty_list():
    assert (
        parse_log_entries("26-13339        0106 Phone - Something Log Information")
        == []
    )


SAMPLE_WITH_TIMESTAMPS = """\
For Date: 05/01/2026  -  Friday
Call   Number   Time   Call   Reason   Action
26-13339        0106 Phone - Telephone Harassment Incident Report Taken
       Call Source:    Telephone
        Primary Id:    SMN - Officer Stephan Nix
  Location/Address:    TIMBERWOOD DR
                       Disp-01:07:39  Enrt-01:39:04  Arvd-02:05:44  Clrd-02:41:21
       Refer To Incident:      26L-426-OF
26-13343        0640 Phone - BOL/ATL Broadcast Log Information
       Call Source:    Telephone
  Location/Address:    POVERTY LN
                       Disp-06:54:31                 Arvd-06:55:08  Clrd-09:04:39
"""


def test_dispatched_at_parsed():
    entries = parse_log_entries(SAMPLE_WITH_TIMESTAMPS)
    e = entries[0]
    assert e["dispatched_at"] == datetime(2026, 5, 1, 1, 7, 39)


def test_arrived_at_parsed():
    entries = parse_log_entries(SAMPLE_WITH_TIMESTAMPS)
    assert entries[0]["arrived_at"] == datetime(2026, 5, 1, 2, 5, 44)


def test_cleared_at_parsed():
    entries = parse_log_entries(SAMPLE_WITH_TIMESTAMPS)
    assert entries[0]["cleared_at"] == datetime(2026, 5, 1, 2, 41, 21)


def test_response_seconds_computed():
    entries = parse_log_entries(SAMPLE_WITH_TIMESTAMPS)
    # Arvd(02:05:44) - Disp(01:07:39) = 58m5s = 3485 seconds
    assert entries[0]["response_seconds"] == 3485


def test_scene_seconds_computed():
    entries = parse_log_entries(SAMPLE_WITH_TIMESTAMPS)
    # Clrd(02:41:21) - Arvd(02:05:44) = 35m37s = 2137 seconds
    assert entries[0]["scene_seconds"] == 2137


def test_enroute_at_none_when_missing():
    entries = parse_log_entries(SAMPLE_WITH_TIMESTAMPS)
    # Second entry (BOL) has no Enrt field
    assert entries[1]["enroute_at"] is None


def test_timestamps_none_when_no_dispatch_line():
    entries = parse_log_entries(SAMPLE_PAGE_BREAK)  # no dispatch timing line
    assert entries[0]["dispatched_at"] is None
    assert entries[0]["response_seconds"] is None


# One fixture and test per parser gap. The layouts follow the sample above.
HEADER = (
    "For Date: 05/11/2026  -  Monday\nCall   Number   Time   Call   Reason   Action\n"
)


def parse_one(entry_text: str) -> dict:
    [entry] = parse_log_entries(HEADER + entry_text)
    return entry


def test_parser_version_is_2_and_the_extractor_version_is_pypdfs():
    assert PARSER_VERSION == 2
    assert pypdf.__version__ == EXTRACTOR_VERSION


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


def test_call_source_comes_from_the_call_source_line():
    entry = parse_one(
        "26-20003        1015 Phone - Suspicious Person Advised\n"
        "       Call Source:    Walk-In\n"
    )

    assert entry["call_source"] == "Walk-In"


def test_call_source_falls_back_to_the_header_when_there_is_no_line():
    entry = parse_one("26-20004        1015 Phone - Suspicious Person Advised\n")

    assert entry["call_source"] == "Phone"


def test_place_code_is_kept_apart_from_the_location():
    entry = parse_one(
        "26-20005        1015 Phone - Suspicious Person Advised\n"
        "  Location/Address:    [L HANNAF] HANNAFORD - PLAINFIELD RD\n"
    )

    assert entry["place_code"] == "L HANNAF"
    assert entry["location"] == "HANNAFORD - PLAINFIELD RD"


def test_place_code_is_none_without_brackets():
    entry = parse_one(
        "26-20006        1015 Phone - Suspicious Person Advised\n"
        "  Location/Address:    EAGLE RIDGE RD\n"
    )

    assert entry["place_code"] is None


def test_officer_code_is_kept_apart_from_the_name():
    entry = parse_one(
        "26-20007        1015 Phone - Suspicious Person Advised\n"
        "        Primary Id:    SMN - Officer Stephan Nix\n"
    )

    assert entry["officer_code"] == "SMN"
    assert entry["officer"] == "Stephan Nix"


def test_officer_code_is_none_without_a_primary_id():
    entry = parse_one("26-20008        1015 Phone - Suspicious Person Advised\n")

    assert entry["officer_code"] is None


def test_every_refer_to_kind_is_kept_in_order():
    entry = parse_one(
        "26-20009        1015 Phone - Motor Vehicle Crash Report Taken\n"
        "       Refer To Incident:      26L-426-OF\n"
        "       Refer To Citation:      26L-77-CT\n"
        "       Refer To Accident:      26L-12-AC\n"
        "       Refer To Arrest:        26L-346-AR\n"
    )

    assert entry["refer_to"] == [
        {"kind": "Incident", "number": "26L-426-OF"},
        {"kind": "Citation", "number": "26L-77-CT"},
        {"kind": "Accident", "number": "26L-12-AC"},
        {"kind": "Arrest", "number": "26L-346-AR"},
    ]
    assert entry["reference_number"] == "26L-426-OF"


def test_refer_to_is_none_when_the_entry_has_no_reference():
    entry = parse_one("26-20010        1015 Phone - Suspicious Person Advised\n")

    assert entry["refer_to"] is None
    assert entry["reference_number"] is None


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


def test_the_disposition_list_has_a_public_name_and_the_old_alias_is_the_same_list():
    from parsers import dispositions

    assert dispositions.DISPOSITIONS
    assert "Incident Report Taken" in dispositions.DISPOSITIONS
    assert dispositions._DISPOSITIONS is dispositions.DISPOSITIONS
