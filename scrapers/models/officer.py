from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OfficerRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    scraped_at: datetime
    rank: str | None = None
    division: str | None = None
    email: str | None = None
    phone: str | None = None
