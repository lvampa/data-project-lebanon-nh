from datetime import date, datetime
from typing import Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class UrlDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    canonical_url: str
    archive_url: Optional[str] = None
    log_date: Optional[date] = None
    state: Literal["pending", "in_progress", "complete", "error"]
    created_at: datetime
    completed_at: Optional[datetime] = None
    raw_text: Optional[str] = None
    entry_count: Optional[int] = None
    error_message: Optional[str] = None
