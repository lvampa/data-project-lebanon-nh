import re
from datetime import date, datetime, timedelta
from typing import Any

# Longest first so alternation matches the most specific disposition
_KNOWN_DISPOSITIONS = [
    "Incident Report Taken",
    "Broadcast Log Information",
    "Criminal Summons Issued",
    "Referred to Other Agency",
    "Traffic Citation Issued",
    "Gone on Arrival",
    "Arrest(s) Made",
    "Log Information",
    "Warning Issued",
    "Report Taken",
    "Assisted Party",
    "Services Rendered",
    "Unable to Locate",
    "Protective Custody",
    "No Action Required",
    "Transport/Escort",
    "Field Interview",
    "Verbal Warning",
    "Vehicle Towed",
    "False Alarm",
    "Unfounded",
    "No Report",
    "Advised",
    "Warning",
]

_DISPOSITION_RE = re.compile(
    r"\s+(" + "|".join(re.escape(d) for d in _KNOWN_DISPOSITIONS) + r")\s*$",
    re.IGNORECASE,
)

# "For Date: 05/01/2026  -  Friday"
_DATE_RE = re.compile(r"For Date:\s*(\d{2}/\d{2}/\d{4})")

# Entry header: "26-13339        0106 Phone - Telephone Harassment Incident Report Taken"
_ENTRY_RE = re.compile(
    r"^(?P<case_number>\d{2}-\d+)\s+(?P<time>\d{4})\s+(?P<call_source>\S+)\s+-\s+(?P<reason_action>.+?)\s*$",
    re.MULTILINE,
)

# "Primary Id:    SMN - Officer Stephan Nix"
_OFFICER_RE = re.compile(r"Primary Id:\s*\S+\s+-\s+(?:Officer\s+)?(.+?)\s*$", re.MULTILINE)

# "Location/Address:    [L TWD4] TIMBERWOOD COMMONS - TIMBERWOOD DR"
_LOCATION_RE = re.compile(r"Location/Address:\s*(?:\[[^\]]*\]\s*)?(.+?)\s*$", re.MULTILINE)

# "Refer To Incident:      26L-426-OF" or "Refer To Arrest:      26L-346-AR"
_REFERENCE_RE = re.compile(r"Refer To (?:Incident|Arrest):\s*(\S+)", re.MULTILINE)

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


def parse_log_entries(text: str) -> list[dict[str, Any]]:
    date_match = _DATE_RE.search(text)
    if not date_match:
        return []

    try:
        log_date = datetime.strptime(date_match.group(1), _DATE_FMT).date()
    except ValueError:
        return []

    clean = _strip_page_headers(text)
    entry_matches = list(_ENTRY_RE.finditer(clean))
    if not entry_matches:
        return []

    entries = []
    for i, m in enumerate(entry_matches):
        case_number = m.group("case_number")
        time_str = m.group("time")
        call_source = m.group("call_source")
        reason_action = m.group("reason_action")

        block_end = entry_matches[i + 1].start() if i + 1 < len(entry_matches) else len(clean)
        block = clean[m.end():block_end]
        raw_text = clean[m.start():block_end].strip()

        disp_match = _DISPOSITION_RE.search(reason_action)
        if disp_match:
            disposition = disp_match.group(1)
            incident_type = reason_action[:disp_match.start()].strip()
        else:
            incident_type = reason_action
            disposition = None

        officer_match = _OFFICER_RE.search(block)
        officer = officer_match.group(1).strip() if officer_match else None

        location_match = _LOCATION_RE.search(block)
        location = location_match.group(1).strip() if location_match else None

        reference_match = _REFERENCE_RE.search(block)
        reference_number = reference_match.group(1).strip() if reference_match else None

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
            reported_at = datetime(log_date.year, log_date.month, log_date.day, hour, minute)
            parse_error = False
        except ValueError:
            reported_at = None
            parse_error = True

        entries.append({
            "case_number": case_number,
            "reported_at": reported_at,
            "call_source": call_source,
            "incident_type": incident_type,
            "disposition": disposition,
            "raw_reason_action": reason_action,
            "location": location,
            "officer": officer,
            "reference_number": reference_number,
            "raw_text": raw_text,
            "parse_error": parse_error,
            "dispatched_at": dispatched_at,
            "enroute_at": enroute_at,
            "arrived_at": arrived_at,
            "cleared_at": cleared_at,
            "response_seconds": response_seconds,
            "scene_seconds": scene_seconds,
        })

    return entries
