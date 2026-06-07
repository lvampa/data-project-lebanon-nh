from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from items.property import PropertyItem
from pipelines import PropertyPipeline
from sqlalchemy.dialects import postgresql


def _sql_strings(call_args_list):
    """Compile SQLAlchemy statements from execute() calls to SQL strings."""
    result = []
    for c in call_args_list:
        stmt = c.args[0]
        try:
            result.append(str(stmt.compile(dialect=postgresql.dialect())))
        except Exception:
            result.append(str(stmt))
    return result


def make_item(**kwargs):
    defaults = dict(
        parcel_id="10001",
        location="123 MAIN ST",
        owner=None,
        owner_address=None,
        land_use=None,
        lot_size_acres=None,
        year_built=None,
        building_sqft=None,
        assessed_total=None,
        assessed_land=None,
        assessed_building=None,
        assessment_year=None,
        detail_url="https://example.com",
        sales=[],
    )
    defaults.update(kwargs)
    return PropertyItem(**defaults)


@patch("pipelines.SessionLocal")
def test_llc_owner_queues_lookup(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_session.execute.return_value.scalar_one.return_value = 1

    pipeline = PropertyPipeline()
    pipeline.open_spider(None)
    pipeline.process_item(make_item(owner="ANAGNOST UPPER VALLEY LLC"), None)

    # Verify an LLC insert was attempted (pg_insert called with Llc table)
    calls = _sql_strings(mock_session.execute.call_args_list)
    assert any("llcs" in c.lower() for c in calls)


@patch("pipelines.SessionLocal")
def test_individual_owner_skips_lookup(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_session.execute.return_value.scalar_one.return_value = 1

    pipeline = PropertyPipeline()
    pipeline.open_spider(None)
    pipeline.process_item(make_item(owner="SMITH, JOHN"), None)

    calls = _sql_strings(mock_session.execute.call_args_list)
    assert not any("llcs" in c.lower() for c in calls)


@patch("pipelines.SessionLocal")
def test_none_owner_skips_lookup(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_session.execute.return_value.scalar_one.return_value = 1

    pipeline = PropertyPipeline()
    pipeline.open_spider(None)
    pipeline.process_item(make_item(owner=None), None)

    calls = _sql_strings(mock_session.execute.call_args_list)
    assert not any("llcs" in c.lower() for c in calls)
