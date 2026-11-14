from unittest.mock import MagicMock, patch

from locations.geocode import GeocodeResult

from api.config import Settings, get_settings
from api.main import app
from api.tests.conftest import ADMIN_TOKEN
from api.tests.sql import compile_pg, executed_stmt, upsert_set_columns


def _make_row(location, count, normalized_address=None, lat=None, lng=None):
    row = MagicMock()
    row.location = location
    row.count = count
    row.normalized_address = normalized_address
    row.lat = lat
    row.lng = lng
    row.kind = None
    row.source = None
    row.needs_review = None
    return row


def test_list_addresses_returns_locations(mock_db, client):
    mock_db.scalar.return_value = 2
    mock_db.execute.return_value.all.return_value = [
        _make_row("TIMBERWOOD DR", 5, "Timberwood Drive", 43.64, -72.25),
        _make_row("EAGLE RIDGE RD", 2, None, None, None),
    ]
    resp = client.get("/api/addresses")

    assert resp.status_code == 200
    data = resp.json()
    assert (data["total"], data["page"], data["per_page"]) == (2, 1, 50)
    items = data["items"]
    assert len(items) == 2
    assert items[0]["raw_address"] == "TIMBERWOOD DR"
    assert items[0]["is_normalized"] is True
    assert items[1]["is_normalized"] is False


def test_list_addresses_pages_in_stable_order(mock_db, client):
    mock_db.scalar.return_value = 0
    mock_db.execute.return_value.all.return_value = []

    resp = client.get("/api/addresses?page=3&per_page=25")

    assert resp.status_code == 200
    compiled = compile_pg(executed_stmt(mock_db))
    assert "ORDER BY count(*) DESC, log_entries.location" in str(compiled)
    assert compiled.params["param_1"] == 25
    assert compiled.params["param_2"] == 50


def _stored(mock_db, lat=None, lng=None, geocoded_via=None):
    stored = MagicMock(lat=lat, lng=lng, geocoded_via=geocoded_via)
    mock_db.execute.return_value.one.return_value = stored


def test_patch_address_upserts_on_raw_address(mock_db, client):
    _stored(mock_db, 43.64, -72.25, "nominatim")
    with patch(
        "api.services.addresses.geocode",
        return_value=GeocodeResult(43.64, -72.25, "exact"),
    ):
        resp = client.patch(
            "/api/addresses/EAGLE%20RIDGE%20RD",
            json={"normalized_address": "Eagle Ridge Road", "notes": "typo"},
        )

    assert resp.status_code == 200
    assert resp.json()["normalized_address"] == "Eagle Ridge Road"
    stmt = executed_stmt(mock_db)
    assert "ON CONFLICT (raw_address) DO UPDATE" in str(compile_pg(stmt))
    params = compile_pg(stmt).params
    assert params["raw_address"] == "EAGLE RIDGE RD"
    assert params["normalized_address"] == "Eagle Ridge Road"
    assert {"normalized_address", "notes", "updated_at"} <= upsert_set_columns(stmt)
    mock_db.add.assert_not_called()
    mock_db.commit.assert_called_once()


def test_patch_address_without_geocode_keeps_existing_coords(mock_db, client):
    _stored(mock_db, 43.64, -72.25, "nominatim")
    with patch("api.services.addresses.geocode") as geocode:
        resp = client.patch(
            "/api/addresses/TIMBERWOOD%20DR",
            json={"normalized_address": "Timberwood Drive", "geocode": False},
        )

    assert resp.status_code == 200
    geocode.assert_not_called()
    stmt = executed_stmt(mock_db)
    assert upsert_set_columns(stmt).isdisjoint({"lat", "lng", "geocoded_via"})
    assert resp.json()["lat"] == 43.64
    assert resp.json()["lng"] == -72.25
    assert resp.json()["geocoded_via"] == "nominatim"


def test_patch_address_geocode_miss_keeps_existing_coords(mock_db, client):
    _stored(mock_db, 43.64, -72.25, "nominatim")
    with patch("api.services.addresses.geocode", return_value=None):
        resp = client.patch(
            "/api/addresses/TIMBERWOOD%20DR",
            json={"normalized_address": "Timberwood Drive", "geocode": True},
        )

    assert resp.status_code == 200
    stmt = executed_stmt(mock_db)
    assert upsert_set_columns(stmt).isdisjoint({"lat", "lng", "geocoded_via"})
    assert resp.json()["lat"] == 43.64


def test_patch_address_geocode_hit_sets_coords(mock_db, client):
    _stored(mock_db, 43.7, -72.3, "nominatim")
    with patch(
        "api.services.addresses.geocode",
        return_value=GeocodeResult(43.7, -72.3, "approximate"),
    ):
        resp = client.patch(
            "/api/addresses/TIMBERWOOD%20DR",
            json={"normalized_address": "Timberwood Drive", "geocode": True},
        )

    assert resp.status_code == 200
    stmt = executed_stmt(mock_db)
    assert {"lat", "lng", "geocoded_via"} <= upsert_set_columns(stmt)
    params = compile_pg(stmt).params
    assert (params["lat"], params["lng"]) == (43.7, -72.3)
    assert params["geocoded_via"] == "nominatim"
    assert params["coordinate_precision"] == "approximate"


def test_patch_address_manual_coords_skip_geocoding(mock_db, client):
    _stored(mock_db, 43.65, -72.26, "manual")
    with patch("api.services.addresses.geocode") as geocode:
        resp = client.patch(
            "/api/addresses/TIMBERWOOD%20DR",
            json={
                "normalized_address": "Timberwood Drive",
                "lat": 43.65,
                "lng": -72.26,
            },
        )

    assert resp.status_code == 200
    geocode.assert_not_called()
    stmt = executed_stmt(mock_db)
    assert {"lat", "lng", "geocoded_via", "coordinate_precision"} <= upsert_set_columns(
        stmt
    )
    params = compile_pg(stmt).params
    assert (params["lat"], params["lng"]) == (43.65, -72.26)
    assert params["geocoded_via"] == "manual"
    assert params["coordinate_precision"] == "exact"
    assert resp.json()["geocoded_via"] == "manual"


def test_patch_address_lat_without_lng_returns_422(mock_db, client):
    resp = client.patch(
        "/api/addresses/TIMBERWOOD%20DR",
        json={"normalized_address": "Timberwood Drive", "lat": 43.65},
    )

    assert resp.status_code == 422
    mock_db.execute.assert_not_called()


def test_patch_address_geocodes_with_configured_contact(mock_db, client):
    _stored(mock_db)
    app.dependency_overrides[get_settings] = lambda: Settings(
        admin_api_token=ADMIN_TOKEN, nominatim_contact="ops@example.com"
    )
    with patch("api.services.addresses.geocode", return_value=None) as geocode:
        resp = client.patch(
            "/api/addresses/TIMBERWOOD%20DR",
            json={"normalized_address": "Timberwood Drive"},
        )

    assert resp.status_code == 200
    geocode.assert_called_once_with(
        "Timberwood Drive, Lebanon, NH, USA", contact="ops@example.com"
    )
