from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlanningMeetingRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    civicclerk_event_id: int
    source_url: str = Field(min_length=1)
    scraped_at: datetime
    title: str | None = None
    category: str | None = None
    meeting_date: datetime | None = None
    location: str | None = None
    status: str | None = None


class PlanningDocumentRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    civicclerk_file_id: int
    civicclerk_event_id: int
    scraped_at: datetime
    file_name: str | None = None
    file_type: str | None = None
    download_url: str | None = None
    raw_text: str | None = None
