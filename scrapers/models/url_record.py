from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class UrlRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    canonical_url: str = Field(min_length=1)
    state: Literal["pending", "in_progress", "complete", "error"]
    created_at: datetime
    archive_url: str | None = None
    log_date: date | None = None
