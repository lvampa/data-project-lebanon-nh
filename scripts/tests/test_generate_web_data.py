import pytest
from scripts.generate_web_data import (
    format_incidents,
    format_stats,
    format_addresses,
    format_staff,
)


def make_log_entry(**kwargs):
    defaults = dict(
        case_number="2026-001",
        reported_at=None,
        call_source="911",
        incident_type="THEFT",
        disposition="Closed",
        location="1 Main St",
        officer="Smith",
        reference_number=None,
        source_url="https://example.com",
    )
    return type("LogEntry", (), {**defaults, **kwargs})()


def make_address_row(**kwargs):
    defaults = dict(
        location="1 Main St",
        count=3,
        normalized_address="1 Main Street",
        lat=43.642,
        lng=-72.252,
    )
    return type("Row", (), {**defaults, **kwargs})()


def make_staff(**kwargs):
    defaults = dict(
        id=1,
        name="Jane Doe",
        title="Patrol Officer",
        department="Police",
        division="Patrol",
        email="jdoe@police.nh.gov",
        phone="(603) 448-1234",
        source_url="https://www.lebanonnh.gov/796/Department-Roster",
    )
    return type("CityStaff", (), {**defaults, **kwargs})()


def test_format_incidents_shape():
    rows = [make_log_entry()]
    result = format_incidents(rows)
    assert isinstance(result, list)
    item = result[0]
    assert item["case_number"] == "2026-001"
    assert item["incident_type"] == "THEFT"
    assert "source_url" in item


def test_format_incidents_none_reported_at():
    rows = [make_log_entry(reported_at=None)]
    result = format_incidents(rows)
    assert result[0]["reported_at"] is None


def test_format_addresses_excludes_no_geocode():
    rows = [
        make_address_row(lat=43.6, lng=-72.2),
        make_address_row(lat=None, lng=None),
    ]
    result = format_addresses(rows)
    assert len(result) == 1
    assert result[0]["lat"] == 43.6


def test_format_staff_shape():
    result = format_staff([make_staff()])
    item = result[0]
    assert item["name"] == "Jane Doe"
    assert item["department"] == "Police"
    assert "scraped_at" not in item


def test_format_stats_shape():
    by_type = [type("R", (), {"incident_type": "THEFT", "count": 5})()]
    by_weekday = [type("R", (), {"dow": 1, "count": 10})()]
    result = format_stats(by_type, by_weekday, total=100)
    assert result["total"] == 100
    assert result["by_type"][0] == {"incident_type": "THEFT", "count": 5}
    assert result["by_weekday"][0]["day"] == "Mon"
    assert result["by_weekday"][0]["count"] == 10
