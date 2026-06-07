from datetime import date, datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class UrlDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: ObjectId | None = Field(default=None, alias="_id")
    canonical_url: str
    archive_url: str | None = None
    log_date: date | None = None
    state: Literal["pending", "in_progress", "complete", "error"]
    created_at: datetime
    completed_at: datetime | None = None
    raw_text: str | None = None
    entry_count: int | None = None
    error_message: str | None = None
