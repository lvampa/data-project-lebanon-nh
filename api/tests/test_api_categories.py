from unittest.mock import MagicMock

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


def _make_row(incident_type, count, category=None, subcategory=None):
    r = MagicMock()
    r.incident_type = incident_type
    r.count = count
    r.category = category
    r.subcategory = subcategory
    return r


def test_list_categories_returns_all_types():
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [
        _make_row("Telephone Harassment", 10, "Disturbance"),
        _make_row("MV Stop", 8, None),
    ]
    client = _client(mock_db)
    resp = client.get("/api/categories")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["raw_incident_type"] == "Telephone Harassment"
    assert data[0]["category"] == "Disturbance"
    assert data[0]["is_categorized"] is True
    assert data[1]["is_categorized"] is False


def test_patch_category_creates_record():
    mock_db = MagicMock()
    mock_db.scalar.return_value = None  # no existing record

    client = _client(mock_db)
    resp = client.patch(
        "/api/categories/MV%20Stop",
        json={"category": "Traffic", "subcategory": None},
    )

    assert resp.status_code == 200
    assert resp.json()["category"] == "Traffic"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_patch_category_updates_existing():
    mock_db = MagicMock()
    existing = MagicMock()
    mock_db.scalar.return_value = existing

    client = _client(mock_db)
    resp = client.patch(
        "/api/categories/MV%20Stop",
        json={"category": "Traffic", "subcategory": "Moving Violation"},
    )

    assert resp.status_code == 200
    assert existing.category == "Traffic"
    assert existing.subcategory == "Moving Violation"
    mock_db.add.assert_not_called()
    mock_db.commit.assert_called_once()
