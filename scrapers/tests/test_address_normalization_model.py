from datetime import datetime, timezone
from postgres.models.address_normalization import AddressNormalization

def test_address_normalization_model_fields():
    now = datetime.now(timezone.utc)
    norm = AddressNormalization(
        raw_address="TIMBERWOOD DR",
        normalized_address="Timberwood Drive",
        lat=43.6425,
        lng=-72.2518,
        geocoded_via="nominatim",
        notes=None,
        created_at=now,
        updated_at=now,
    )
    assert norm.raw_address == "TIMBERWOOD DR"
    assert norm.normalized_address == "Timberwood Drive"
    assert norm.lat == 43.6425
    assert norm.lng == -72.2518
    assert norm.geocoded_via == "nominatim"
