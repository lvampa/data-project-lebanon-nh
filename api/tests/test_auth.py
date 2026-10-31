from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app
from api.tests.conftest import ADMIN_TOKEN

WRITE_ROUTES = [
    (
        "/api/addresses/1%20Main%20St",
        {"normalized_address": "1 Main St", "geocode": False},
    ),
    ("/api/categories/MV%20Stop", {"category": "Traffic", "subcategory": None}),
    ("/api/llcs/1/status", {"lookup_status": "complete"}),
]


@pytest.fixture
def mock_db():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


@pytest.mark.parametrize(("path", "body"), WRITE_ROUTES)
def test_write_without_token_returns_401(mock_db, path, body):
    resp = TestClient(app).patch(path, json=body)

    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
    mock_db.commit.assert_not_called()


@pytest.mark.parametrize(("path", "body"), WRITE_ROUTES)
def test_write_with_wrong_token_returns_401(mock_db, path, body):
    headers = {"Authorization": "Bearer wrong-token"}
    resp = TestClient(app).patch(path, json=body, headers=headers)

    assert resp.status_code == 401
    mock_db.commit.assert_not_called()


def test_write_with_correct_token_passes_through(mock_db):
    mock_db.scalar.return_value = None
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    resp = TestClient(app).patch(
        "/api/categories/MV%20Stop",
        json={"category": "Traffic", "subcategory": None},
        headers=headers,
    )

    assert resp.status_code == 200
    mock_db.commit.assert_called_once()


def test_write_rejected_when_token_not_configured(mock_db, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN")
    headers = {"Authorization": "Bearer anything"}
    resp = TestClient(app).patch(
        "/api/categories/MV%20Stop",
        json={"category": "Traffic", "subcategory": None},
        headers=headers,
    )

    assert resp.status_code == 401
    mock_db.commit.assert_not_called()


def test_reads_need_no_token(mock_db):
    mock_db.execute.return_value.all.return_value = []

    resp = TestClient(app).get("/api/categories")

    assert resp.status_code == 200
