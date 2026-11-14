"""The dispositions the parser splits off the end of a log entry's reason and action.

The log prints one string, such as "Telephone Harassment Incident Report Taken". Only
a list of known endings tells the incident type from the disposition.

Changing this list changes parsed values, so it comes with a PARSER_VERSION bump and
a reprocess. Until older entries are reprocessed, data check 14.3 fails the daily
build, because they still carry a newly listed disposition inside their incident type.
"""

import re

DISPOSITIONS = (
    "Incident Report Taken",
    "Broadcast Log Information",
    "Criminal Summons Issued",
    "Referred to Other Agency",
    "Traffic Citation Issued",
    "Paperwork NOT Served",
    "Transported/Relayed",
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
    "Paperwork Served",
    "Summons Issued",
    "Removed Hazard",
    "Investigated",
    "False Alarm",
    "Unfounded",
    "No Report",
    "Advised",
    "Warning",
)

# The old private name, kept in case anything still imports it.
_DISPOSITIONS = DISPOSITIONS

# Longest first, so a suffix such as "Paperwork NOT Served" is not cut short.
_DISPOSITION_AT_END = re.compile(
    r"\s+("
    + "|".join(re.escape(d) for d in sorted(DISPOSITIONS, key=len, reverse=True))
    + r")\s*$",
    re.IGNORECASE,
)


def split_reason_action(reason_action: str) -> tuple[str, str | None]:
    """The incident type and the disposition, or the whole text and None."""
    match = _DISPOSITION_AT_END.search(reason_action)
    if match is None:
        return reason_action, None
    return reason_action[: match.start()].strip(), match.group(1)
