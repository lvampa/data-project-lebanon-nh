from unittest.mock import MagicMock

from api.tests.sql import compile_pg, executed_stmt, upsert_set_columns


def _make_row(incident_type, count, category=None, subcategory=None):
    r = MagicMock()
    r.incident_type = incident_type
    r.count = count
    r.category = category
    r.subcategory = subcategory
    return r


def test_list_categories_returns_all_types(mock_db, client):
    mock_db.execute.return_value.all.return_value = [
        _make_row("Telephone Harassment", 10, "Disturbance"),
        _make_row("MV Stop", 8, None),
    ]
    resp = client.get("/api/categories")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["raw_incident_type"] == "Telephone Harassment"
    assert data[0]["category"] == "Disturbance"
    assert data[0]["is_categorized"] is True
    assert data[1]["is_categorized"] is False


def test_patch_category_upserts_on_raw_incident_type(mock_db, client):
    resp = client.patch(
        "/api/categories/MV%20Stop",
        json={"category": "Traffic", "subcategory": "Moving Violation"},
    )

    assert resp.status_code == 200
    assert resp.json()["category"] == "Traffic"
    stmt = executed_stmt(mock_db)
    assert "ON CONFLICT (raw_incident_type) DO UPDATE" in str(compile_pg(stmt))
    params = compile_pg(stmt).params
    assert params["raw_incident_type"] == "MV Stop"
    assert params["category"] == "Traffic"
    assert params["subcategory"] == "Moving Violation"
    assert upsert_set_columns(stmt) == {"category", "subcategory", "updated_at"}
    mock_db.add.assert_not_called()
    mock_db.commit.assert_called_once()
