"""Pytest plugin that runs MongoDB tests against a database named `*_test`.

It loads through the `pytest11` entry point, so every suite in the workspace gets it
without a conftest.
"""

import os
from collections.abc import Iterator
from typing import Any

import pytest
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

TEST_DATABASE = os.environ.get("TEST_MONGO_DB", "scraped_data_test")

# The mongo package builds its shared client from the environment when it is first
# imported, so this has to be set before any test module or conftest imports it.
os.environ["MONGO_DB"] = TEST_DATABASE

ARCHIVE_COLLECTION = "raw_sources"


def is_test_database(name: str | None) -> bool:
    return bool(name) and name.endswith("_test")


def pytest_configure(config: pytest.Config) -> None:
    if not is_test_database(TEST_DATABASE):
        pytest.exit(
            f"Refusing to run tests: MongoDB database {TEST_DATABASE!r} "
            "does not end in '_test'.",
            returncode=pytest.ExitCode.USAGE_ERROR,
        )


@pytest.fixture(scope="session")
def mongo_test_db() -> Database[dict[str, Any]]:
    """The MongoDB test database, after checking the server answers."""
    from mongo import db

    # mongo may have been imported before this plugin set MONGO_DB.
    if not is_test_database(db.default_db):
        pytest.exit(
            f"Refusing to run tests: the MongoDB client points at "
            f"{db.default_db!r}, which does not end in '_test'.",
            returncode=pytest.ExitCode.USAGE_ERROR,
        )
    database = db.get_collection(ARCHIVE_COLLECTION).database
    # A short timeout of its own, so a stopped server fails in seconds, not 30.
    probe = MongoClient(
        host=db.host,
        port=db.port,
        username=db.username,
        password=db.password,
        serverSelectionTimeoutMS=2000,
    )
    try:
        probe.admin.command("ping")
    except PyMongoError:
        unreachable = True
    else:
        unreachable = False
    finally:
        probe.close()
    # Failing outside the except block keeps the driver's traceback out of the report.
    if unreachable:
        pytest.fail(
            f"MongoDB tests need MongoDB at {db.host}:{db.port}. "
            "Start it with `docker compose up -d mongo`.",
            pytrace=False,
        )
    return database


@pytest.fixture
def raw_sources(
    mongo_test_db: Database[dict[str, Any]],
) -> Iterator[Collection[dict[str, Any]]]:
    """The archive collection, dropped after the test so the database stays empty."""
    collection = mongo_test_db[ARCHIVE_COLLECTION]
    collection.drop()
    try:
        yield collection
    finally:
        collection.drop()
