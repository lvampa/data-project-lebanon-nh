from unittest.mock import MagicMock, patch

from api.deps import Paging
from api.schemas import AddressUpdate
from api.services import addresses
from api.tests.sql import compile_pg, executed_stmt, upsert_set_columns


def test_list_addresses_joins_normalizations_and_pages():
    db = MagicMock()
    db.scalar.return_value = 1
    db.execute.return_value.all.return_value = [
        MagicMock(
            location="TIMBERWOOD DR",
            count=5,
            normalized_address=None,
            lat=None,
            lng=None,
        )
    ]

    page = addresses.list_addresses(db, Paging(page=3, per_page=25))

    assert page.total == 1
    assert page.items[0].raw_address == "TIMBERWOOD DR"
    assert page.items[0].is_normalized is False
    compiled = compile_pg(executed_stmt(db))
    assert "LEFT OUTER JOIN address_normalizations" in str(compiled)
    assert "ORDER BY count(*) DESC, log_entries.location" in str(compiled)
    assert compiled.params["param_1"] == 25
    assert compiled.params["param_2"] == 50


def test_update_address_upserts_geocoded_coordinates_and_commits():
    db = MagicMock()
    db.execute.return_value.one.return_value = MagicMock(
        lat=43.7, lng=-72.3, geocoded_via="nominatim"
    )
    update = AddressUpdate(normalized_address="Timberwood Drive")

    with patch(
        "api.services.addresses.geocode_nominatim", return_value=(43.7, -72.3)
    ) as geocode:
        result = addresses.update_address(db, "TIMBERWOOD DR", update)

    geocode.assert_called_once_with("Timberwood Drive")
    stmt = executed_stmt(db)
    assert "ON CONFLICT (raw_address) DO UPDATE" in str(compile_pg(stmt))
    assert {"normalized_address", "lat", "lng", "geocoded_via"} <= (
        upsert_set_columns(stmt)
    )
    db.commit.assert_called_once()
    assert (result.lat, result.lng, result.geocoded_via) == (43.7, -72.3, "nominatim")
