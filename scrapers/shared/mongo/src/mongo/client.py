import os

from pymongo import MongoClient
from pymongo.collection import Collection

class MongoDB:
    _client: MongoClient | None = None

    def __init__(self) -> None:
        self.host = os.environ.get("MONGO_HOST", "localhost")
        self.port = int(os.environ.get("MONGO_PORT", 27017))
        self.username = os.environ.get("MONGO_USER", "admin")
        self.password = os.environ.get("MONGO_PASSWORD", "changeme")
        self.default_db = os.environ.get("MONGO_DB", "scraped_data")

    def _connect(self) -> None:
        if self._client is None:
            self._client = MongoClient(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
            )

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_collection(self, collection: str, db: str | None = None) -> Collection:
        if self._client is None:
            self._connect()
        return self._client[db or self.default_db][collection]
