from datetime import date, datetime
from pydantic import BaseModel


class Incident(BaseModel):
    case_number: str
    reported_at: datetime | None
    call_source: str | None
    incident_type: str | None
    disposition: str | None
    location: str | None
    officer: str | None
    reference_number: str | None
    source_url: str | None

    model_config = {"from_attributes": True}


class IncidentsResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[Incident]


class TypeStat(BaseModel):
    incident_type: str
    count: int


class HourStat(BaseModel):
    hour: int
    count: int


class WeekdayStat(BaseModel):
    day: str
    count: int


class AddressRecord(BaseModel):
    raw_address: str
    count: int
    normalized_address: str | None
    lat: float | None
    lng: float | None
    is_normalized: bool


class AddressUpdate(BaseModel):
    normalized_address: str
    notes: str | None = None
    geocode: bool = True


class AddressResult(BaseModel):
    raw_address: str
    normalized_address: str
    lat: float | None
    lng: float | None
    geocoded_via: str | None


class CategoryRecord(BaseModel):
    raw_incident_type: str
    count: int
    category: str | None
    subcategory: str | None
    is_categorized: bool


class CategoryUpdate(BaseModel):
    category: str
    subcategory: str | None = None


class CategoryResult(BaseModel):
    raw_incident_type: str
    category: str
    subcategory: str | None


class LlcPrincipal(BaseModel):
    name: str
    title: str
    address: str | None = None


class Llc(BaseModel):
    id: int
    name: str
    raw_owner_name: str | None
    lookup_status: str
    nh_business_id: str | None
    business_status: str | None
    formation_date: date | None
    business_email: str | None
    phone: str | None
    registered_agent: str | None
    registered_agent_address: str | None
    principals: list | None
    last_looked_up_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class LlcsResponse(BaseModel):
    total: int
    items: list[Llc]


class LlcStatusUpdate(BaseModel):
    lookup_status: str
