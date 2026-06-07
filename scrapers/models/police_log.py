from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PoliceLogRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_url: str
    scraped_at: datetime
    case_number: str | None = None
    reported_at: datetime | None = None
    call_source: str | None = None
    incident_type: str | None = None
    disposition: str | None = None
    raw_reason_action: str | None = None
    location: str | None = None
    officer: str | None = None
    reference_number: str | None = None
    dispatched_at: datetime | None = None
    enroute_at: datetime | None = None
    arrived_at: datetime | None = None
    cleared_at: datetime | None = None
    response_seconds: int | None = None
    scene_seconds: int | None = None
    raw_text: str | None = None
    parse_error: bool = False
