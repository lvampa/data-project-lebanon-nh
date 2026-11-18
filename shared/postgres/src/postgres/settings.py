from functools import cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings
from sqlalchemy import URL


class PostgresSettings(BaseSettings):
    # The aliases carry the full variable names so a missing password is reported
    # as POSTGRES_PASSWORD. The password has no default on purpose.
    user: str = Field("app", validation_alias="POSTGRES_USER")
    password: SecretStr = Field(validation_alias="POSTGRES_PASSWORD")
    host: str = Field("localhost", validation_alias="POSTGRES_HOST")
    port: int = Field(5432, validation_alias="POSTGRES_PORT")
    db: str = Field("app", validation_alias="POSTGRES_DB")

    @property
    def url(self) -> URL:
        return URL.create(
            "postgresql+psycopg2",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.db,
        )


@cache
def get_postgres_settings() -> PostgresSettings:
    return PostgresSettings()
