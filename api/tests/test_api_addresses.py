from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def _client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app)


def _make_row(location, count, normalized_address=None, lat=None, lng=None):
    row = MagicMock()
    row.location = location
    row.count = count
    row.normalized_address = normalized_address
    row.lat = lat
    row.lng = lng
    return row


def test_list_addresses_returns_all_locations():
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [
        _make_row("TIMBERWOOD DR", 5, "Timberwood Drive", 43.64, -72.25),
        _make_row("EAGLE RIDGE RD", 2, None, None, None),
    ]
    client = _client(mock_db)
    resp = client.get("/api/addresses")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["raw_address"] == "TIMBERWOOD DR"
    assert data[0]["is_normalized"] is True
    assert data[1]["is_normalized"] is False


def test_patch_address_creates_normalization():
    mock_db = MagicMock()
    mock_db.scalar.return_value = None  # no existing record

    with patch("api.routers.addresses.geocode_nominatim", return_value=(43.64, -72.25)):
        client = _client(mock_db)
        resp = client.patch(
            "/api/addresses/EAGLE%20RIDGE%20RD",
            json={"normalized_address": "Eagle Ridge Road", "geocode": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["normalized_address"] == "Eagle Ridge Road"
    assert data["lat"] == 43.64
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_patch_address_updates_existing():
    mock_db = MagicMock()
    existing = MagicMock()
    mock_db.scalar.return_value = existing

    with patch("api.routers.addresses.geocode_nominatim", return_value=(43.64, -72.25)):
        client = _client(mock_db)
        resp = client.patch(
            "/api/addresses/TIMBERWOOD%20DR",
            json={"normalized_address": "Timberwood Drive", "geocode": True},
        )

    assert resp.status_code == 200
    assert existing.normalized_address == "Timberwood Drive"
    mock_db.add.assert_not_called()
    mock_db.commit.assert_called_once()
