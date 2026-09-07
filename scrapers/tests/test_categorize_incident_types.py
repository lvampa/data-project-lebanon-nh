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
    assert rows[0] == {
        "incident_type": "FD Alarm",
        "category": "Fire",
        "subcategory": "Alarm Activation",
    }
    assert rows[2]["category"] == "Traffic"


def test_parse_strips_markdown_fences():
    rows = parse_claude_response(VALID_JSON_WITH_PREAMBLE)
    assert len(rows) == 1
    assert rows[0]["category"] == "Fire"


def test_parse_missing_subcategory_defaults_to_none():
    rows = parse_claude_response(MISSING_FIELD_JSON)
    assert rows[0]["subcategory"] is None


def test_parse_invalid_category_raises():
    with pytest.raises(ValueError, match="Invalid category"):
        parse_claude_response(INVALID_CATEGORY_JSON)


def test_parse_empty_list():
    rows = parse_claude_response("[]")
    assert rows == []


# --- upsert_categories ---


def test_upsert_categories_executes_for_each_row():
    session = MagicMock()
    rows = [
        {
            "incident_type": "FD Alarm",
            "category": "Fire",
            "subcategory": "Alarm Activation",
        },
        {
            "incident_type": "MV Accident",
            "category": "Traffic",
            "subcategory": "Accident",
        },
    ]
    upsert_categories(session, rows)
    assert session.execute.call_count == 2


def test_upsert_categories_noop_on_empty():
    session = MagicMock()
    upsert_categories(session, [])
    session.execute.assert_not_called()


def test_upsert_categories_commits():
    session = MagicMock()
    upsert_categories(
        session,
        [
            {
                "incident_type": "FD Alarm",
                "category": "Fire",
                "subcategory": "Alarm Activation",
            },
        ],
    )
    session.commit.assert_called_once()


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
