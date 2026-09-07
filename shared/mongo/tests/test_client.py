from unittest.mock import patch

import pytest
from mongo.client import MongoDB


@pytest.fixture(autouse=True)
def reset_client():
    MongoDB._client = None
    yield
    MongoDB._client = None


@pytest.fixture
def db():
    return MongoDB()


def test_defaults(db):
    assert db.host == "localhost"
    assert db.port == 27017
    assert db.username == "admin"
    assert db.password == "changeme"
    assert db.default_db == "scraped_data"


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
        password="changeme",
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
