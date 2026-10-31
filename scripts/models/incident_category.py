from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

IncidentCategory = Literal["Fire", "EMS", "Police", "Traffic", "Administrative"]
INCIDENT_CATEGORIES: tuple[str, ...] = get_args(IncidentCategory)


class IncidentCategoryRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    incident_type: str = Field(min_length=1)
    category: IncidentCategory
    subcategory: str | None = None

    @field_validator("subcategory")
    @classmethod
    def blank_subcategory_is_none(cls, value: str | None) -> str | None:
        return value or None
