import subprocess
import sys
from unittest.mock import patch

import pytest
from mongo import get_db
from mongo.client import MongoDB
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def no_mongo_env(monkeypatch):
    # The defaults are under test, so settings from the shell or CI must not leak in.
    for name in (
        "MONGO_HOST",
        "MONGO_PORT",
        "MONGO_USER",
        "MONGO_PASSWORD",
        "MONGO_DB",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("MONGO_PASSWORD", "secret")
    return MongoDB()


def test_defaults_cover_everything_but_the_password(db):
    assert db.host == "localhost"
    assert db.port == 27017
    assert db.username == "admin"
    assert db.password == "secret"
    assert db.default_db == "scraped_data"


def test_a_missing_password_is_an_error_that_names_the_variable():
    with pytest.raises(ValidationError, match="MONGO_PASSWORD"):
        MongoDB()


def test_get_db_returns_the_same_client_every_call(db):
    assert get_db() is get_db()


IMPORT_READS_NOTHING = """
import os
for name in list(os.environ):
    if name.startswith("MONGO_"):
        del os.environ[name]

import mongo
from mongo.client import get_db

assert get_db.cache_info().currsize == 0
"""


def test_importing_mongo_reads_no_settings():
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_READS_NOTHING],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_env_vars(monkeypatch, db):
    monkeypatch.setenv("MONGO_HOST", "myhost")
    monkeypatch.setenv("MONGO_PORT", "1234")
    monkeypatch.setenv("MONGO_USER", "user")
    monkeypatch.setenv("MONGO_PASSWORD", "secret")
    monkeypatch.setenv("MONGO_DB", "mydb")
    db2 = MongoDB()
    assert db2.host == "myhost"
    assert db2.port == 1234
    assert db2.username == "user"
    assert db2.password == "secret"
    assert db2.default_db == "mydb"


@patch("mongo.client.MongoClient")
def test_connect(mock_client, db):
    db._connect()
    mock_client.assert_called_once_with(
        host="localhost",
        port=27017,
        username="admin",
        password="secret",
    )
    assert db._client is mock_client.return_value


@patch("mongo.client.MongoClient")
def test_connect_idempotent(mock_client, db):
    db._connect()
    db._connect()
    mock_client.assert_called_once()


@patch("mongo.client.MongoClient")
def test_disconnect(mock_client, db):
    db._connect()
    db.disconnect()
    mock_client.return_value.close.assert_called_once()
    assert db._client is None


def test_disconnect_when_not_connected(db):
    db.disconnect()  # should not raise


@patch("mongo.client.MongoClient")
def test_get_collection_uses_default_db(mock_client, db):
    db.get_collection("articles")
    mock_client.return_value.__getitem__.assert_called_with("scraped_data")


@patch("mongo.client.MongoClient")
def test_get_collection_uses_provided_db(mock_client, db):
    db.get_collection("articles", db="other_db")
    mock_client.return_value.__getitem__.assert_called_with("other_db")


@patch("mongo.client.MongoClient")
def test_get_collection_triggers_connect(mock_client, db):
    assert db._client is None
    db.get_collection("articles")
    mock_client.assert_called_once()
