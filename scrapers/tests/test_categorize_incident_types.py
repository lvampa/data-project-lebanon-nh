# scrapers/tests/test_categorize_incident_types.py
from unittest.mock import MagicMock, patch

import pytest
from maintenance.categorize_incident_types import (
    fetch_uncategorized,
    parse_claude_response,
    upsert_categories,
)

# --- fetch_uncategorized ---


def test_fetch_uncategorized_returns_distinct_types():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = [
        "FD Alarm",
        "Telephone Harassment",
        "MV Accident",
    ]
    result = fetch_uncategorized(session)
    assert result == ["FD Alarm", "Telephone Harassment", "MV Accident"]
    session.execute.assert_called_once()


def test_fetch_uncategorized_calls_execute():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    fetch_uncategorized(session)
    session.execute.assert_called_once()


# --- parse_claude_response ---

VALID_JSON = """
[
  {"incident_type": "FD Alarm", "category": "Fire", "subcategory": "Alarm Activation"},
  {"incident_type": "Telephone Harassment", "category": "Police", "subcategory": "Harassment"},
  {"incident_type": "MV Accident", "category": "Traffic", "subcategory": "Accident"}
]
"""

VALID_JSON_WITH_PREAMBLE = """
Here are the categorizations:

```json
[
  {"incident_type": "FD Alarm", "category": "Fire", "subcategory": "Alarm Activation"}
]
```
"""

MISSING_FIELD_JSON = """
[
  {"incident_type": "FD Alarm", "category": "Fire"}
]
"""

INVALID_CATEGORY_JSON = """
[
  {"incident_type": "FD Alarm", "category": "Unknown", "subcategory": "Whatever"}
]
"""


def test_parse_valid_json():
    rows = parse_claude_response(VALID_JSON)
    assert len(rows) == 3
    assert rows[0].model_dump() == {
        "incident_type": "FD Alarm",
        "category": "Fire",
        "subcategory": "Alarm Activation",
    }
    assert rows[2].category == "Traffic"


def test_parse_strips_markdown_fences():
    rows = parse_claude_response(VALID_JSON_WITH_PREAMBLE)
    assert len(rows) == 1
    assert rows[0].category == "Fire"


def test_parse_missing_subcategory_defaults_to_none():
    rows = parse_claude_response(MISSING_FIELD_JSON)
    assert rows[0].subcategory is None


def test_parse_invalid_category_raises():
    with pytest.raises(ValueError, match="category"):
        parse_claude_response(INVALID_CATEGORY_JSON)


def test_parse_empty_list():
    rows = parse_claude_response("[]")
    assert rows == []


# --- upsert_categories ---


def test_upsert_categories_is_the_shared_ingest_upsert():
    from scripts.ingest import import_incident_categories

    assert upsert_categories is import_incident_categories.upsert_categories


def test_prompt_lists_every_valid_category():
    from maintenance.categorize_incident_types import _PROMPT_TEMPLATE

    from scripts.models import INCIDENT_CATEGORIES

    for category in INCIDENT_CATEGORIES:
        assert f'"{category}"' in _PROMPT_TEMPLATE


import json

# --- dump_uncategorized ---


def test_dump_uncategorized_prints_json(capsys):
    from maintenance.categorize_incident_types import dump_uncategorized

    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = [
        "FD Alarm",
        "MV Accident",
    ]
    dump_uncategorized(session)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data == ["FD Alarm", "MV Accident"]


def test_dump_uncategorized_empty(capsys):
    from maintenance.categorize_incident_types import dump_uncategorized

    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    dump_uncategorized(session)
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []


# --- import_from_stdin ---


def test_import_from_stdin_upserts(monkeypatch):
    import io

    from maintenance.categorize_incident_types import import_from_stdin

    categories = [
        {
            "incident_type": "FD Alarm",
            "category": "Fire",
            "subcategory": "Alarm Activation",
        }
    ]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(categories)))
    session = MagicMock()
    import_from_stdin(session)
    session.execute.assert_called_once()
    session.commit.assert_called_once()


def test_import_from_stdin_rejects_unknown_category(monkeypatch):
    import io

    from maintenance.categorize_incident_types import import_from_stdin

    categories = [{"incident_type": "FD Alarm", "category": "Unknown"}]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(categories)))
    session = MagicMock()
    with pytest.raises(ValueError, match="category"):
        import_from_stdin(session)
    session.execute.assert_not_called()


# --- run_via_cli ---


def test_run_via_cli_calls_subprocess():
    from maintenance.categorize_incident_types import run_via_cli

    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = ["FD Alarm"]

    mock_result = MagicMock()
    mock_result.stdout = '[{"incident_type": "FD Alarm", "category": "Fire", "subcategory": "Alarm Activation"}]'

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        run_via_cli(session)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "claude"
        assert "--print" in args

    session.commit.assert_called_once()


def test_run_via_cli_noop_when_nothing_to_categorize():
    from maintenance.categorize_incident_types import run_via_cli

    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []

    with patch("subprocess.run") as mock_run:
        run_via_cli(session)
        mock_run.assert_not_called()
