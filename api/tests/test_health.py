from sqlalchemy.exc import OperationalError

from api.tests.sql import compile_pg, executed_stmt


def test_healthz_ok_when_postgres_responds(mock_db, client):
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json() == {"postgres": "ok"}
    assert str(compile_pg(executed_stmt(mock_db))) == "SELECT 1"


def test_healthz_503_names_postgres_when_it_fails(mock_db, client):
    mock_db.execute.side_effect = OperationalError("SELECT 1", {}, Exception("down"))

    resp = client.get("/healthz")

    assert resp.status_code == 503
    assert resp.json() == {"postgres": "error"}


def test_requests_are_traced(capfire, client):
    client.get("/healthz")

    span_names = {s["name"] for s in capfire.exporter.exported_spans_as_dict()}
    assert "GET /healthz" in span_names
