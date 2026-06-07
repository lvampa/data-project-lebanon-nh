from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SaleRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sale_date: date | None = None
    sale_price: int | None = None
    grantee: str | None = None
    grantor: str | None = None

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
    owner_address: str | None = None
    land_use: str | None = None
    lot_size_acres: float | None = None
    year_built: int | None = None
    building_sqft: int | None = None
    assessed_land: int | None = None
    assessed_building: int | None = None
    assessed_total: int | None = None
    assessment_year: int | None = None
    detail_url: str | None = None
    sales: list[SaleRecord] = Field(default_factory=list)
