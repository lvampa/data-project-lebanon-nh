import re
from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def _whole_number(value: object) -> object:
    """'$1,140,700' and '6,848' as 1140700 and 6848. A blank is None."""
    if not isinstance(value, str):
        return value
    digits = re.sub(r"[^0-9]", "", value)
    return int(digits) if digits else None


def _decimal(value: object) -> object:
    if not isinstance(value, str):
        return value
    cleaned = re.sub(r"[^0-9.]", "", value)
    try:
        return float(cleaned)
    except ValueError:
        return None


Whole = Annotated[int | None, BeforeValidator(_whole_number)]
Decimal = Annotated[float | None, BeforeValidator(_decimal)]


class SaleRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # The owner the sale made. The seller is the owner in the next row down.
    owner: str | None = None
    sale_price: Whole = None
    certificate: str | None = None
    book_page: str | None = None
    instrument: str | None = None
    sale_date: date | None = None

    @field_validator("owner", "certificate", "book_page", "instrument")
    @classmethod
    def blank_is_none(cls, v: str | None) -> str | None:
        return v or None

    @field_validator("sale_date", mode="before")
    @classmethod
    def parse_sale_date(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        try:
            m, d, y = v.strip().split("/")
            return date(int(y), int(m), int(d))
        except Exception:
            return None


class PropertyRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    parcel_id: str = Field(min_length=1)
    location: str | None = None
    owner: str | None = None
    co_owner: str | None = None
    owner_address: str | None = None
    mblu: str | None = None
    account_number: str | None = None
    use_code: str | None = None
    land_use: str | None = None
    zone: str | None = None
    neighborhood: str | None = None
    lot_size_acres: Decimal = None
    year_built: Whole = None
    building_sqft: Whole = None
    assessed_land: Whole = None
    assessed_building: Whole = None
    assessed_total: Whole = None
    assessment_year: Whole = None
    appraised_land: Whole = None
    appraised_building: Whole = None
    appraised_total: Whole = None
    land: dict[str, Any] | None = None
    buildings: list[dict[str, Any]] | None = None
    outbuildings: list[dict[str, Any]] | None = None
    extra_features: list[dict[str, Any]] | None = None
    value_history: dict[str, Any] | None = None
    detail_url: str | None = None
    sales: list[SaleRecord] = Field(default_factory=list)
