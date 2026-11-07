import pytest
from mongo import db
from mongo_testing.plugin import is_test_database


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("scraped_data_test", True),
        ("x_test", True),
        ("scraped_data", False),
        ("test_scraped_data", False),
    ],
)
def test_only_names_ending_in_test_count_as_test_databases(name, expected):
    assert is_test_database(name) is expected


def test_the_shared_client_points_at_the_test_database():
    assert is_test_database(db.default_db)


def test_writes_go_to_the_test_database(raw_sources):
    raw_sources.insert_one({"source": "probe"})

    assert raw_sources.database.name == db.default_db
    assert raw_sources.count_documents({}) == 1


def test_the_archive_collection_is_empty_at_the_start_of_each_test(raw_sources):
    # Runs after the test above, which left a document behind before teardown.
    assert raw_sources.count_documents({}) == 0
