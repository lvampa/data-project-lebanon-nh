from functools import cache
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection

from .settings import MongoSettings, get_mongo_settings


class MongoDB:
    def __init__(self, settings: MongoSettings | None = None) -> None:
        self._client: MongoClient[dict[str, Any]] | None = None
        settings = settings or get_mongo_settings()
        self.host = settings.host
        self.port = settings.port
        self.username = settings.user
        self.password = settings.password
        self.default_db = settings.db

    def _connect(self) -> MongoClient[dict[str, Any]]:
        if self._client is None:
            self._client = MongoClient(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password.get_secret_value(),
            )
        return self._client

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_collection(
        self, collection: str, db: str | None = None
    ) -> Collection[dict[str, Any]]:
        client = self._connect()
        return client[db or self.default_db][collection]


@cache
def get_db() -> MongoDB:
    """The process-wide client, built on first use so .env can load first."""
    return MongoDB()
