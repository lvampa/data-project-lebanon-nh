from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class LlcPrincipal(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    title: str | None = None
    address: str | None = None


class LlcLookupRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nh_business_id: str | None = None
    business_status: str | None = None
    formation_date: date | None = None
    business_email: str | None = None
    phone: str | None = None
    registered_agent: str | None = None
    registered_agent_address: str | None = None
    principals: list[LlcPrincipal] | None = None
