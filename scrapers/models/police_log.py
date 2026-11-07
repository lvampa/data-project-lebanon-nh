from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class Reference(BaseModel):
    """One "Refer To" line: the kind of record and its number."""

    kind: str = Field(min_length=1)
    number: str = Field(min_length=1)


class PoliceLogRecord(BaseModel):
    """One log entry as it is written to `log_entries`. Field names are column names."""

    # A parser key with no column is a bug, so it fails here, not at the insert.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_url: str = Field(min_length=1)
    log_date: date
    case_number: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)
    scraped_at: datetime
    parser_version: int
    reported_at: datetime | None = None
    call_source: str | None = None
    incident_type: str | None = None
    disposition: str | None = None
    disposition_unmatched: bool = False
    raw_reason_action: str | None = None
    location: str | None = None
    place_code: str | None = None
    officer: str | None = None
    officer_code: str | None = None
    reference_number: str | None = None
    refer_to: list[Reference] | None = None
    dispatched_at: datetime | None = None
    enroute_at: datetime | None = None
    arrived_at: datetime | None = None
    cleared_at: datetime | None = None
    response_seconds: int | None = None
    scene_seconds: int | None = None
    parse_error: bool = False
