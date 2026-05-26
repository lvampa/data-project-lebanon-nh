from datetime import datetime, timezone
from postgres.models.incident_type_category import IncidentTypeCategory

def test_incident_type_category_fields():
    now = datetime.now(timezone.utc)
    cat = IncidentTypeCategory(
        raw_incident_type="Telephone Harassment",
        category="Disturbance",
        subcategory=None,
        created_at=now,
        updated_at=now,
    )
    assert cat.raw_incident_type == "Telephone Harassment"
    assert cat.category == "Disturbance"
    assert cat.subcategory is None
