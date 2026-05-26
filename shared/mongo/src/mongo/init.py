from .client import MongoDB


def init_indexes(mongo: MongoDB | None = None) -> None:
    db = mongo or MongoDB()
    urls = db.get_collection("urls")
    urls.create_index("state")
    urls.create_index("canonical_url", unique=True)
    print("Mongo indexes initialized.")
