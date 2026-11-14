"""Police log entry text in the raw archive: each entry's cut of its PDF's text."""

import json
from datetime import datetime

from .archive import ArchivedResponse

# One version per entry, keyed by case number: its text as the parser cut it.
ENTRY_TEXT_SOURCE = "police_log_entry_text"


def entry_text(
    *,
    source_url: str,
    raw_text: str,
    raw_reason_action: str | None,
    parser_version: int | None,
    fetched_at: datetime,
    spider: str,
) -> ArchivedResponse:
    """One entry's text as an archive version.

    The parser version is part of the body, so a parser bump stores a new version
    even when the text is the same, and the history shows which parser cut what.
    """
    body = json.dumps(
        {
            "raw_text": raw_text,
            "raw_reason_action": raw_reason_action,
            "source_url": source_url,
            "parser_version": parser_version,
        },
        # Sorted, so the same values always hash to the same version.
        sort_keys=True,
    ).encode()
    return ArchivedResponse(
        url=source_url,
        status=200,
        content_type="application/json",
        body=body,
        fetched_at=fetched_at,
        spider=spider,
    )
