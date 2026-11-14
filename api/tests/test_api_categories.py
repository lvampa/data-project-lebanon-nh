from unittest.mock import MagicMock

from api.tests.sql import compile_pg, executed_stmt, upsert_set_columns


def _make_row(incident_type, count, category=None, normalized_type=None, source=None):
    r = MagicMock()
    r.incident_type = incident_type
    r.count = count
    r.category = category
    r.normalized_type = normalized_type
    r.source = source
    r.needs_review = None
    return r


def test_list_categories_returns_types(mock_db, client):
    mock_db.scalar.return_value = 2
    mock_db.execute.return_value.all.return_value = [
        _make_row("Telephone Harassment", 10, "Disturbance"),
        _make_row("MV Stop", 8, None),
    ]
    resp = client.get("/api/categories")

    assert resp.status_code == 200
    data = resp.json()
    assert (data["total"], data["page"], data["per_page"]) == (2, 1, 50)
    items = data["items"]
    assert len(items) == 2
    assert items[0]["raw_incident_type"] == "Telephone Harassment"
    assert items[0]["category"] == "Disturbance"
    assert items[0]["is_categorized"] is True
    assert items[1]["is_categorized"] is False


def test_list_categories_pages_in_stable_order(mock_db, client):
    mock_db.scalar.return_value = 0
    mock_db.execute.return_value.all.return_value = []

    resp = client.get("/api/categories?page=2&per_page=100")

    assert resp.status_code == 200
    compiled = compile_pg(executed_stmt(mock_db))
    assert "ORDER BY count(*) DESC, log_entries.incident_type" in str(compiled)
    assert compiled.params["param_1"] == 100
    assert compiled.params["param_2"] == 100


def test_patch_category_upserts_on_raw_incident_type(mock_db, client):
    resp = client.patch(
        "/api/categories/MV%20Stop",
        json={"category": "Traffic", "normalized_type": "Moving Violation"},
    )

    assert resp.status_code == 200
    assert resp.json()["category"] == "Traffic"
    stmt = executed_stmt(mock_db)
    assert "ON CONFLICT (raw_incident_type) DO UPDATE" in str(compile_pg(stmt))
    params = compile_pg(stmt).params
    assert params["raw_incident_type"] == "MV Stop"
    assert params["category"] == "Traffic"
    assert params["normalized_type"] == "Moving Violation"
    assert upsert_set_columns(stmt) == {
        "category",
        "normalized_type",
        "source",
        "needs_review",
        "prompt_version",
        "updated_at",
    }
    mock_db.add.assert_not_called()
    mock_db.commit.assert_called_once()
