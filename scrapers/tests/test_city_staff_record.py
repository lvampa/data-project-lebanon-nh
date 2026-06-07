import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from models.city_staff import CityStaffRecord


def make_staff(**kwargs):
    defaults = dict(
        name="Jane Smith",
        title="Chief of Police",
        department="Police",
        division="Patrol",
        email="jane@lebanon.gov",
        phone="603-555-0100",
        source_url="https://www.lebcity.com/staff",
        scraped_at=datetime.now(timezone.utc),
    )
    return {**defaults, **kwargs}


def test_city_staff_record_shape():
    record = CityStaffRecord.model_validate(make_staff())
    assert record.name == "Jane Smith"
    assert record.department == "Police"


def test_city_staff_record_strips_whitespace():
    record = CityStaffRecord.model_validate(make_staff(name="  Jane Smith  "))
    assert record.name == "Jane Smith"


def test_city_staff_record_null_optional_fields():
    record = CityStaffRecord.model_validate(make_staff(title=None, division=None, email=None, phone=None))
    assert record.title is None
    assert record.division is None


def test_city_staff_record_missing_required_raises():
    data = make_staff()
    del data["name"]
    with pytest.raises(ValidationError):
        CityStaffRecord.model_validate(data)


def test_city_staff_record_blank_name_raises():
    with pytest.raises(ValidationError):
        CityStaffRecord.model_validate(make_staff(name=""))


def test_city_staff_record_whitespace_name_raises():
    with pytest.raises(ValidationError):
        CityStaffRecord.model_validate(make_staff(name="   "))
