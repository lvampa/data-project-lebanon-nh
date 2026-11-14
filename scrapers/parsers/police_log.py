import re
from datetime import date, datetime, timedelta
from typing import Any

import pypdf

from .dispositions import split_reason_action

# Bump when parsing behavior changes, then reprocess so stored entries pick it up.
PARSER_VERSION = 2

# The text extractor's version. A pypdf upgrade can change the extracted text, so it
# counts as a parser change: bump PARSER_VERSION with it, then reprocess.
EXTRACTOR_VERSION = pypdf.__version__

# "For Date: 05/01/2026  -  Friday"
_DATE_RE = re.compile(r"For Date:\s*(\d{2}/\d{2}/\d{4})")

# Entry header: "26-13339        0106 Phone - Telephone Harassment Incident Report Taken"
_ENTRY_RE = re.compile(
    r"^(?P<case_number>\d{2}-\d+)\s+(?P<time>\d{4})\s+(?P<call_source>\S+)\s+-\s+(?P<reason_action>.+?)\s*$",
    re.MULTILINE,
)

# "Call Source:    Telephone"
_CALL_SOURCE_RE = re.compile(r"Call Source:\s*(.+?)\s*$", re.MULTILINE)

# "Primary Id:    SMN - Officer Stephan Nix"
_OFFICER_RE = re.compile(
    r"Primary Id:\s*(?P<code>\S+)\s+-\s+(?:Officer\s+)?(?P<name>.+?)\s*$",
    re.MULTILINE,
)

# "Location/Address:    [L TWD4] TIMBERWOOD COMMONS - TIMBERWOOD DR"; the bracket is
# the place code. A few entries print "Vicinity of:" instead.
_LOCATION_RES = (
    re.compile(
        r"Location/Address:\s*(?:\[(?P<place_code>[^\]]*)\]\s*)?(?P<location>.+?)\s*$",
        re.MULTILINE,
    ),
    re.compile(
        r"Vicinity of:\s*(?:\[(?P<place_code>[^\]]*)\]\s*)?(?P<location>.+?)\s*$",
        re.MULTILINE,
    ),
)

# "Refer To Incident:      26L-426-OF", and the same for Arrest, Citation, Accident
_REFERENCE_RE = re.compile(r"Refer To (?P<kind>[A-Za-z]+):\s*(?P<number>\S+)")

_DISPATCH_RE = re.compile(
    r"Disp-(?P<disp>\d{2}:\d{2}:\d{2})"
    r"(?:\s+Enrt-(?P<enrt>\d{2}:\d{2}:\d{2}))?"
    r"(?:\s+Arvd-(?P<arvd>\d{2}:\d{2}:\d{2}))?"
    r"(?:\s+Clrd-(?P<clrd>\d{2}:\d{2}:\d{2}))?",
    re.MULTILINE,
)


def _parse_ts(time_str: str | None, log_date: date) -> datetime | None:
    if not time_str:
        return None
    h, m, s = map(int, time_str.split(":"))
    return datetime(log_date.year, log_date.month, log_date.day, h, m, s)


def _advance(dt: datetime | None, ref: datetime | None) -> datetime | None:
    """Advance dt by one day if it crossed midnight past ref."""
    if dt and ref and dt < ref:
        return dt + timedelta(days=1)
    return dt


_DATE_FMT = "%m/%d/%Y"


def _strip_page_headers(text: str) -> str:
    text = re.sub(r" Lebanon Police Department Page:.*?\n", "\n", text)
    text = re.sub(r"  Dispatch Log  From:.*?\n", "\n", text)
    return text


# Any line that opens with a case number, whether or not the rest of it parses.
_HEADER_LINE_RE = re.compile(r"^\d{2}-\d+\s", re.MULTILINE)


def parse_log_date(text: str) -> date | None:
    date_match = _DATE_RE.search(text)
    if not date_match:
        return None
    try:
        return datetime.strptime(date_match.group(1), _DATE_FMT).date()
    except ValueError:
        return None


def count_header_lines(text: str) -> int:
    return len(_HEADER_LINE_RE.findall(_strip_page_headers(text)))


def _location(block: str) -> tuple[str | None, str | None]:
    """The location and its place code. A Location/Address line wins over Vicinity."""
    for pattern in _LOCATION_RES:
        match = pattern.search(block)
        if match:
            place_code = (match.group("place_code") or "").strip() or None
            return match.group("location").strip(), place_code
    return None, None


def _references(block: str) -> list[dict[str, str]] | None:
    found = [m.groupdict() for m in _REFERENCE_RE.finditer(block)]
    return found or None


def parse_log_entries(text: str) -> list[dict[str, Any]]:
    log_date = parse_log_date(text)
    if log_date is None:
        return []

    clean = _strip_page_headers(text)
    entry_matches = list(_ENTRY_RE.finditer(clean))
    if not entry_matches:
        return []

    entries = []
    for i, m in enumerate(entry_matches):
        case_number = m.group("case_number")
        time_str = m.group("time")
        header_call_source = m.group("call_source")
        reason_action = m.group("reason_action")

        block_end = (
            entry_matches[i + 1].start() if i + 1 < len(entry_matches) else len(clean)
        )
        block = clean[m.end() : block_end]
        raw_text = clean[m.start() : block_end].strip()

        incident_type, disposition = split_reason_action(reason_action)

        call_source_match = _CALL_SOURCE_RE.search(block)
        call_source = (
            call_source_match.group(1) if call_source_match else header_call_source
        )

        officer_match = _OFFICER_RE.search(block)
        officer = officer_match.group("name").strip() if officer_match else None
        officer_code = officer_match.group("code") if officer_match else None

        location, place_code = _location(block)

        refer_to = _references(block)
        reference_number = refer_to[0]["number"] if refer_to else None

        dm = _DISPATCH_RE.search(block)
        dispatched_at = enroute_at = arrived_at = cleared_at = None
        response_seconds = scene_seconds = None
        if dm:
            dispatched_at = _parse_ts(dm.group("disp"), log_date)
            enroute_at = _advance(_parse_ts(dm.group("enrt"), log_date), dispatched_at)
            arrived_at = _advance(
                _parse_ts(dm.group("arvd"), log_date),
                enroute_at or dispatched_at,
            )
            cleared_at = _advance(
                _parse_ts(dm.group("clrd"), log_date),
                arrived_at or enroute_at or dispatched_at,
            )
            if dispatched_at and arrived_at:
                response_seconds = int((arrived_at - dispatched_at).total_seconds())
            if arrived_at and cleared_at:
                scene_seconds = int((cleared_at - arrived_at).total_seconds())

        try:
            hour, minute = int(time_str[:2]), int(time_str[2:])
            reported_at = datetime(
                log_date.year, log_date.month, log_date.day, hour, minute
            )
            parse_error = False
        except ValueError:
            reported_at = None
            parse_error = True

        entries.append(
            {
                "case_number": case_number,
                "reported_at": reported_at,
                "call_source": call_source,
                "incident_type": incident_type,
                "disposition": disposition,
                "disposition_unmatched": disposition is None,
                "raw_reason_action": reason_action,
                "location": location,
                "place_code": place_code,
                "officer": officer,
                "officer_code": officer_code,
                "reference_number": reference_number,
                "refer_to": refer_to,
                "raw_text": raw_text,
                "parse_error": parse_error,
                "dispatched_at": dispatched_at,
                "enroute_at": enroute_at,
                "arrived_at": arrived_at,
                "cleared_at": cleared_at,
                "response_seconds": response_seconds,
                "scene_seconds": scene_seconds,
            }
        )

    return entries
