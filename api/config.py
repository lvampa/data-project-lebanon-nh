from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3001"]
    admin_api_token: str | None = None
    nominatim_contact: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_on_commas(cls, value: object) -> object:
        return value.split(",") if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
