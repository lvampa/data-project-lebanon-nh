import pytest
from unittest.mock import MagicMock


# --- fetch_uncategorized ---

from scripts.export.export_incident_types import fetch_uncategorized


def test_fetch_uncategorized_returns_list():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = [
        "FD Alarm", "Telephone Harassment", "MV Accident"
    ]
    result = fetch_uncategorized(session)
    assert result == ["FD Alarm", "Telephone Harassment", "MV Accident"]


def test_fetch_uncategorized_calls_execute():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    fetch_uncategorized(session)
    session.execute.assert_called_once()


def test_fetch_uncategorized_returns_empty_when_no_rows():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    assert fetch_uncategorized(session) == []

from scripts.ingest.import_incident_categories import parse_categories, upsert_categories

VALID_JSON = '[{"incident_type": "FD Alarm", "category": "Fire", "subcategory": "Alarm Activation"}, {"incident_type": "MV Accident", "category": "Traffic", "subcategory": "Accident"}]'
MISSING_SUBCATEGORY_JSON = '[{"incident_type": "FD Alarm", "category": "Fire"}]'
INVALID_CATEGORY_JSON = '[{"incident_type": "FD Alarm", "category": "Unknown", "subcategory": "Whatever"}]'
MARKDOWN_FENCED_JSON = '```json\n[{"incident_type": "FD Alarm", "category": "Fire", "subcategory": "Alarm"}]\n```'


# --- parse_categories ---

def test_parse_valid_json():
    rows = parse_categories(VALID_JSON)
    assert len(rows) == 2
    assert rows[0] == {"incident_type": "FD Alarm", "category": "Fire", "subcategory": "Alarm Activation"}
    assert rows[1]["category"] == "Traffic"


def test_parse_missing_subcategory_defaults_to_none():
    rows = parse_categories(MISSING_SUBCATEGORY_JSON)
    assert rows[0]["subcategory"] is None


def test_parse_invalid_category_raises():
    with pytest.raises(ValueError, match="Invalid category"):
        parse_categories(INVALID_CATEGORY_JSON)


def test_parse_strips_markdown_fences():
    rows = parse_categories(MARKDOWN_FENCED_JSON)
    assert len(rows) == 1
    assert rows[0]["category"] == "Fire"


def test_parse_empty_list():
    assert parse_categories("[]") == []


# --- upsert_categories ---

def test_upsert_executes_for_each_row():
    session = MagicMock()
    rows = [
        {"incident_type": "FD Alarm", "category": "Fire", "subcategory": "Alarm Activation"},
        {"incident_type": "MV Accident", "category": "Traffic", "subcategory": "Accident"},
    ]
    upsert_categories(session, rows)
    assert session.execute.call_count == 2
    session.commit.assert_called_once()


def test_upsert_noop_on_empty():
    session = MagicMock()
    upsert_categories(session, [])
    session.execute.assert_not_called()
    session.commit.assert_not_called()
