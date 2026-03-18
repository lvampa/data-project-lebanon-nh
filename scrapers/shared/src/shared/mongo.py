import os

from pymongo import MongoClient
from pymongo.collection import Collection


class MongoDB:
    _instance: "MongoDB | None" = None
    _client: MongoClient | None = None

    def __new__(cls) -> "MongoDB":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> None:
        if self._client is None:
            self._client = MongoClient(
                host=os.environ.get("MONGO_HOST", "localhost"),
                port=int(os.environ.get("MONGO_PORT", 27017)),
                username=os.environ.get("MONGO_USER", "admin"),
                password=os.environ.get("MONGO_PASSWORD", "changeme"),
            )

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_collection(self, collection: str, db: str | None = None) -> Collection:
        if self._client is None:
            self.connect()
        db_name = db or os.environ.get("MONGO_DB", "scraped_data")
        return self._client[db_name][collection]


db = MongoDB()
