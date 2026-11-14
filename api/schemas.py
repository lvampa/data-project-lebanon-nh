from datetime import date, datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, model_validator

# The five incident categories. scripts/models/incident_category.py holds the same list
# for the AI side; a test keeps the two equal.
Category = Literal["Fire", "EMS", "Police", "Traffic", "Administrative"]
CATEGORIES: tuple[str, ...] = get_args(Category)
LocationKind = Literal["address", "intersection", "place", "highway"]
Source = Literal["rule", "ai", "human"]


class Page[T](BaseModel):
    total: int
    page: int
    per_page: int
    items: list[T]


class Incident(BaseModel):
    case_number: str | None
    reported_at: datetime | None
    call_source: str | None
    incident_type: str | None
    disposition: str | None
    location: str | None
    officer: str | None
    reference_number: str | None
    source_url: str

    model_config = {"from_attributes": True}


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
    kind: str | None
    source: str | None
    needs_review: bool
    lat: float | None
    lng: float | None
    is_normalized: bool


class AddressUpdate(BaseModel):
    normalized_address: str
    kind: LocationKind | None = None
    notes: str | None = None
    geocode: bool = True
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def lat_and_lng_together(self) -> "AddressUpdate":
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat and lng must be set together")
        return self


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
    normalized_type: str | None
    # Mirrors normalized_type, so the current admin screen keeps showing a value.
    # Remove it when the admin screen is rebuilt.
    subcategory: str | None
    source: str | None
    needs_review: bool
    is_categorized: bool


class CategoryUpdate(BaseModel):
    category: Category
    normalized_type: str | None = None


class CategoryResult(BaseModel):
    raw_incident_type: str
    category: str
    normalized_type: str | None


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
    principals: list[LlcPrincipal] | None
    last_looked_up_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


LookupStatus = Literal["pending", "in_progress", "complete", "error", "skipped"]


class LlcStatusUpdate(BaseModel):
    lookup_status: LookupStatus


class SearchResult(BaseModel):
    id: int
    entity_type: str
    score: float
    data: dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    normalized_query: str | None
    results: dict[str, list[SearchResult]]
