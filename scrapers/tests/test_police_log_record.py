import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from models.police_log import PoliceLogRecord


def make_log(**kwargs):
    defaults = dict(
        source_url="https://example.com/log.pdf",
        scraped_at=datetime.now(timezone.utc),
        case_number="2025-001",
        reported_at=datetime.now(timezone.utc),
        call_source="911",
        incident_type="TRAFFIC STOP",
        disposition="GONE ON ARRIVAL",
        raw_reason_action="SPEEDING",
        location="123 MAIN ST",
        officer="SMITH",
        reference_number="REF-001",
        dispatched_at=None,
        enroute_at=None,
        arrived_at=None,
        cleared_at=None,
        response_seconds=None,
        scene_seconds=None,
        raw_text="raw text here",
        parse_error=False,
    )
    return {**defaults, **kwargs}


def test_police_log_record_shape():
    record = PoliceLogRecord.model_validate(make_log())
    assert record.source_url == "https://example.com/log.pdf"
    assert record.incident_type == "TRAFFIC STOP"
    assert record.parse_error is False


def test_police_log_record_parse_error_defaults_false():
    data = make_log()
    del data["parse_error"]
    record = PoliceLogRecord.model_validate(data)
    assert record.parse_error is False


def test_police_log_record_null_optional_fields():
    record = PoliceLogRecord.model_validate(make_log(
        case_number=None, incident_type=None, location=None
    ))
    assert record.case_number is None
    assert record.incident_type is None
    assert record.location is None


def test_police_log_record_strips_whitespace():
    record = PoliceLogRecord.model_validate(make_log(location="  MAIN ST  "))
    assert record.location == "MAIN ST"


def test_police_log_record_missing_source_url_raises():
    data = make_log()
    del data["source_url"]
    with pytest.raises(ValidationError):
        PoliceLogRecord.model_validate(data)
