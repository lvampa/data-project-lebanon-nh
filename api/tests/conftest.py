import pytest

ADMIN_TOKEN = "test-token"


@pytest.fixture(autouse=True)
def admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", ADMIN_TOKEN)
