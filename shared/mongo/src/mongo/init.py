from pymongo import ASCENDING, DESCENDING

from .archive import COLLECTION as ARCHIVE_COLLECTION
from .client import MongoDB


def init_indexes(mongo: MongoDB | None = None) -> None:
    db = mongo or MongoDB()
    urls = db.get_collection("urls")
    urls.create_index("state")
    urls.create_index("canonical_url", unique=True)

    archive = db.get_collection(ARCHIVE_COLLECTION)
    # The upsert key: one document per distinct body of one source key.
    archive.create_index(
        [("source", ASCENDING), ("source_key", ASCENDING), ("content_hash", ASCENDING)],
        unique=True,
    )
    # Newest version first, for replay and for listing one key's versions.
    archive.create_index(
        [
            ("source", ASCENDING),
            ("source_key", ASCENDING),
            ("first_fetched_at", DESCENDING),
        ]
    )
    # Per-source counts for the check command.
    archive.create_index([("source", ASCENDING), ("last_seen_at", ASCENDING)])
    print("Mongo indexes initialized.")
