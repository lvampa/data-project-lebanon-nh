from datetime import UTC, datetime

from postgres.models.log_entry import LogEntry


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
