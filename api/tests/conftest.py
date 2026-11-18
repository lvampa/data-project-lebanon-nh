from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.config import get_settings
from api.deps import get_session
from api.main import create_app

ADMIN_TOKEN = "test-token"


@pytest.fixture(autouse=True)
def admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", ADMIN_TOKEN)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(app, mock_db):
    app.dependency_overrides[get_session] = lambda: mock_db
    yield TestClient(app, headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    app.dependency_overrides.clear()
