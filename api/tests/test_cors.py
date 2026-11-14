import pytest
from fastapi.testclient import TestClient

from api.main import app

ADMIN_ORIGIN = "http://localhost:3001"
OTHER_ORIGIN = "https://example.com"


@pytest.fixture
def client():
    return TestClient(app)


def test_get_from_admin_origin_gets_allow_origin_header(client):
    resp = client.get("/openapi.json", headers={"Origin": ADMIN_ORIGIN})
    assert resp.headers["access-control-allow-origin"] == ADMIN_ORIGIN


def test_get_from_other_origin_gets_no_allow_origin_header(client):
    resp = client.get("/openapi.json", headers={"Origin": OTHER_ORIGIN})
    assert "access-control-allow-origin" not in resp.headers


def test_preflight_from_admin_origin_is_allowed(client):
    resp = client.options(
        "/api/incidents",
        headers={"Origin": ADMIN_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ADMIN_ORIGIN


def test_preflight_from_other_origin_is_rejected(client):
    resp = client.options(
        "/api/incidents",
        headers={"Origin": OTHER_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in resp.headers
