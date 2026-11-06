from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from api.deps import get_es
from api.main import app
from api.tests.sql import compile_pg, executed_stmt


@pytest.fixture
def mock_es():
    es = MagicMock()
    es.ping.return_value = True
    app.dependency_overrides[get_es] = lambda: es
    return es


def test_healthz_ok_when_postgres_and_es_respond(mock_db, mock_es, client):
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json() == {"postgres": "ok", "elasticsearch": "ok"}
    assert str(compile_pg(executed_stmt(mock_db))) == "SELECT 1"
    mock_es.ping.assert_called_once()


def test_healthz_503_names_postgres_when_it_fails(mock_db, mock_es, client):
    mock_db.execute.side_effect = OperationalError("SELECT 1", {}, Exception("down"))

    resp = client.get("/healthz")

    assert resp.status_code == 503
    assert resp.json() == {"postgres": "error", "elasticsearch": "ok"}


def test_healthz_503_names_elasticsearch_when_it_fails(mock_db, mock_es, client):
    mock_es.ping.return_value = False

    resp = client.get("/healthz")

    assert resp.status_code == 503
    assert resp.json() == {"postgres": "ok", "elasticsearch": "error"}


def test_requests_are_traced(capfire, mock_es, client):
    client.get("/healthz")

    span_names = {s["name"] for s in capfire.exporter.exported_spans_as_dict()}
    assert "GET /healthz" in span_names
