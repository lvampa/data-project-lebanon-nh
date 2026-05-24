from mongo import db


def main() -> None:
    urls = db.get_collection("urls")
    urls.create_index("state")
    urls.create_index("canonical_url", unique=True)
    print("Mongo indexes initialized.")


if __name__ == "__main__":
    main()
