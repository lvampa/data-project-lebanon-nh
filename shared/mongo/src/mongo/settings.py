from functools import cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class MongoSettings(BaseSettings):
    # The aliases carry the full variable names so a missing password is reported
    # as MONGO_PASSWORD. The password has no default on purpose.
    user: str = Field("admin", validation_alias="MONGO_USER")
    password: SecretStr = Field(validation_alias="MONGO_PASSWORD")
    host: str = Field("localhost", validation_alias="MONGO_HOST")
    port: int = Field(27017, validation_alias="MONGO_PORT")
    db: str = Field("scraped_data", validation_alias="MONGO_DB")


@cache
def get_mongo_settings() -> MongoSettings:
    return MongoSettings()
