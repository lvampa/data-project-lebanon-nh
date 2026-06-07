from datetime import datetime

from parsers.police_log import parse_log_entries

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
    assert e["call_source"] == "Phone"
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
    assert e["call_source"] == "Phone"
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
