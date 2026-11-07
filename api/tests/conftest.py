from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.config import get_settings
from api.deps import get_db
from api.main import app

ADMIN_TOKEN = "test-token"


@pytest.fixture(autouse=True)
def admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", ADMIN_TOKEN)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(app, headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    app.dependency_overrides.clear()
