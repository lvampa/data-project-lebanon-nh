import os
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection


class MongoDB:
    def __init__(self) -> None:
        self._client: MongoClient[dict[str, Any]] | None = None
        self.host = os.environ.get("MONGO_HOST", "localhost")
        self.port = int(os.environ.get("MONGO_PORT", 27017))
        self.username = os.environ.get("MONGO_USER", "admin")
        self.password = os.environ.get("MONGO_PASSWORD", "changeme")
        self.default_db = os.environ.get("MONGO_DB", "scraped_data")

    def _connect(self) -> MongoClient[dict[str, Any]]:
        if self._client is None:
            self._client = MongoClient(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
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
