import json
from datetime import datetime
from unittest.mock import MagicMock, patch


def _make_entry(**kwargs):
    defaults = {
        "case_number": "26-13339",
        "reported_at": datetime(2026, 5, 1, 1, 6),
        "incident_type": "Telephone Harassment",
        "disposition": "Incident Report Taken",
        "call_source": "Phone",
        "location": "TIMBERWOOD DR",
        "officer": "Stephan Nix",
        "source_url": "https://example.com/a.pdf",
        "normalized_address": None,
        "lat": None,
        "lng": None,
        "category": None,
        "subcategory": None,
        "response_seconds": None,
        "scene_seconds": None,
        "parse_error": False,
    }
    defaults.update(kwargs)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def test_generate_report_writes_json_files(tmp_path):
    entry = _make_entry()
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [entry]
    mock_db.scalar.side_effect = [42, datetime(2026, 1, 1), datetime(2026, 5, 1)]

    with (
        patch("scripts.generate_report.SessionLocal", return_value=mock_db),
        patch("scripts.generate_report.OUTPUT_DIR", tmp_path),
    ):
        from scripts.generate_report import generate

        generate()

    assert (tmp_path / "incidents.json").exists()
    assert (tmp_path / "summary.json").exists()

    incidents = json.loads((tmp_path / "incidents.json").read_text())
    assert incidents[0]["case_number"] == "26-13339"

    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["total_incidents"] == 42
