from functools import lru_cache
from typing import Annotated

from postgres import PostgresSettings, get_postgres_settings
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    postgres: PostgresSettings = Field(default_factory=get_postgres_settings)
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
