import pytest
from pydantic import ValidationError

from scripts.models import INCIDENT_CATEGORIES, IncidentCategoryRecord


def test_accepts_known_category():
    record = IncidentCategoryRecord.model_validate(
        {"incident_type": "FD Alarm", "category": "Fire", "subcategory": "Alarm"}
    )
    assert record.category == "Fire"
    assert record.subcategory == "Alarm"


def test_blank_subcategory_becomes_none():
    record = IncidentCategoryRecord.model_validate(
        {"incident_type": "FD Alarm", "category": "Fire", "subcategory": ""}
    )
    assert record.subcategory is None


def test_rejects_unknown_category():
    with pytest.raises(ValidationError, match="category"):
        IncidentCategoryRecord.model_validate(
            {"incident_type": "FD Alarm", "category": "Unknown"}
        )


def test_rejects_missing_incident_type():
    with pytest.raises(ValidationError, match="incident_type"):
        IncidentCategoryRecord.model_validate({"category": "Fire"})


def test_category_list_matches_prompt_order():
    assert INCIDENT_CATEGORIES == ("Fire", "EMS", "Police", "Traffic", "Administrative")
