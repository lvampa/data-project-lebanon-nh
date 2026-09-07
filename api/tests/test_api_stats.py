from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def _client_with_mock_db(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app)


def _make_row(**kwargs):
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


def test_stats_by_type_returns_list():
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [
        _make_row(incident_type="Telephone Harassment", count=12),
        _make_row(incident_type="MV Stop", count=8),
    ]
    client = _client_with_mock_db(mock_db)
    resp = client.get("/api/stats/by-type")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["incident_type"] == "Telephone Harassment"
    assert data[0]["count"] == 12


def test_stats_by_hour_returns_buckets():
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [
        _make_row(hour=0, count=3),
        _make_row(hour=14, count=10),
    ]
    client = _client_with_mock_db(mock_db)
    resp = client.get("/api/stats/by-hour")

    assert resp.status_code == 200
    data = resp.json()
    assert all("hour" in r and "count" in r for r in data)


def test_stats_by_weekday_returns_day_names():
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [
        _make_row(dow=0, count=5),
        _make_row(dow=1, count=8),
    ]
    client = _client_with_mock_db(mock_db)
    resp = client.get("/api/stats/by-weekday")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["day"] == "Sun"
    assert data[1]["day"] == "Mon"
