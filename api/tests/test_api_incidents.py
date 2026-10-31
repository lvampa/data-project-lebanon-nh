from datetime import UTC, datetime

import pytest
from postgres.models.log_entry import LogEntry

from api.tests.sql import compile_pg


def _make_entry(**kwargs) -> LogEntry:
    defaults = {
        "id": 1,
        "source_url": "https://example.com/a.pdf",
        "case_number": "26-13339",
        "reported_at": datetime(2026, 5, 1, 1, 6),
        "call_source": "Phone",
        "incident_type": "Telephone Harassment",
        "disposition": "Incident Report Taken",
        "raw_reason_action": "Telephone Harassment Incident Report Taken",
        "location": "TIMBERWOOD DR",
        "officer": "Stephan Nix",
        "reference_number": "26L-426-OF",
        "raw_text": "26-13339 0106 ...",
        "parse_error": False,
        "scraped_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return LogEntry(**defaults)


def test_incidents_returns_list(mock_db, client):
    entry = _make_entry()
    mock_db.scalar.return_value = 1
    mock_db.scalars.return_value.all.return_value = [entry]

    resp = client.get("/api/incidents")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["case_number"] == "26-13339"
    assert data["items"][0]["incident_type"] == "Telephone Harassment"


def test_incidents_serializes_null_case_number(mock_db, client):
    mock_db.scalar.return_value = 1
    mock_db.scalars.return_value.all.return_value = [_make_entry(case_number=None)]

    resp = client.get("/api/incidents")

    assert resp.status_code == 200
    assert resp.json()["items"][0]["case_number"] is None


def test_incidents_filters_by_incident_type(mock_db, client):
    mock_db.scalar.return_value = 0
    mock_db.scalars.return_value.all.return_value = []

    resp = client.get("/api/incidents?incident_type=Harassment")

    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_incidents_pagination_defaults(mock_db, client):
    mock_db.scalar.return_value = 0
    mock_db.scalars.return_value.all.return_value = []

    resp = client.get("/api/incidents")

    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["per_page"] == 50


@pytest.mark.parametrize("field", ["incident_type", "disposition", "officer"])
def test_incidents_filter_matches_wildcards_literally(mock_db, client, field):
    mock_db.scalar.return_value = 0
    mock_db.scalars.return_value.all.return_value = []

    resp = client.get(f"/api/incidents?{field}=50%25_off")

    assert resp.status_code == 200
    compiled = compile_pg(mock_db.scalars.call_args.args[0])
    assert "ESCAPE '/'" in str(compiled)
    assert "50/%/_off" in compiled.params.values()


@pytest.mark.parametrize("query", ["page=0", "page=-1", "per_page=0", "per_page=201"])
def test_incidents_rejects_out_of_range_paging(mock_db, client, query):
    resp = client.get(f"/api/incidents?{query}")

    assert resp.status_code == 422
    mock_db.scalars.assert_not_called()


def test_incidents_order_is_stable_across_pages(mock_db, client):
    mock_db.scalar.return_value = 0
    mock_db.scalars.return_value.all.return_value = []

    resp = client.get("/api/incidents?page=3&per_page=20")

    assert resp.status_code == 200
    compiled = compile_pg(mock_db.scalars.call_args.args[0])
    assert (
        "ORDER BY log_entries.reported_at DESC NULLS LAST, log_entries.id DESC"
        in str(compiled)
    )
    assert compiled.params["param_1"] == 20
    assert compiled.params["param_2"] == 40
