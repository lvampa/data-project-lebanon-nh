import os

from pymongo import MongoClient
from pymongo.collection import Collection


class MongoPipeline:
    collection_name = "police_logs"

    def open_spider(self, spider):
        user = os.environ.get("MONGO_USER", "admin")
        password = os.environ.get("MONGO_PASSWORD", "changeme")
        host = os.environ.get("MONGO_HOST", "localhost")
        port = int(os.environ.get("MONGO_PORT", 27017))
        db_name = os.environ.get("MONGO_DB", "lebanon")

        self.client = MongoClient(host, port, username=user, password=password)
        self.collection: Collection = self.client[db_name][self.collection_name]
        self.collection.create_index("source_url", unique=True)

    def close_spider(self, spider):
        self.client.close()

    def process_item(self, item, spider):
        self.collection.update_one(
            {"source_url": item["source_url"]},
            {"$set": dict(item)},
            upsert=True,
        )
        return item
