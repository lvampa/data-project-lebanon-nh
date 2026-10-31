from unittest.mock import MagicMock, patch

from api.tests.sql import compile_pg, executed_stmt, upsert_set_columns


def _make_row(location, count, normalized_address=None, lat=None, lng=None):
    row = MagicMock()
    row.location = location
    row.count = count
    row.normalized_address = normalized_address
    row.lat = lat
    row.lng = lng
    return row


def test_list_addresses_returns_all_locations(mock_db, client):
    mock_db.execute.return_value.all.return_value = [
        _make_row("TIMBERWOOD DR", 5, "Timberwood Drive", 43.64, -72.25),
        _make_row("EAGLE RIDGE RD", 2, None, None, None),
    ]
    resp = client.get("/api/addresses")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["raw_address"] == "TIMBERWOOD DR"
    assert data[0]["is_normalized"] is True
    assert data[1]["is_normalized"] is False


def test_patch_address_upserts_on_raw_address(mock_db, client):
    with patch("api.routers.addresses.geocode_nominatim", return_value=(43.64, -72.25)):
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
