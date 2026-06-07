import pytest
from unittest.mock import MagicMock


# --- fetch_uncategorized ---

from scripts.export_incident_types import fetch_uncategorized


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
