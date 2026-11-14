from unittest.mock import MagicMock

from api.deps import NormalizationFilter, Paging
from api.schemas import CategoryUpdate
from api.services import categories
from api.tests.sql import compile_pg, executed_stmt, upsert_set_columns


def test_list_categories_joins_categories_and_pages():
    db = MagicMock()
    db.scalar.return_value = 1
    db.execute.return_value.all.return_value = [
        MagicMock(
            incident_type="MV Stop",
            count=8,
            category="Traffic",
            normalized_type=None,
            source=None,
            needs_review=None,
        )
    ]

    page = categories.list_categories(
        db, Paging(page=2, per_page=100), NormalizationFilter(None, None, None)
    )

    assert page.total == 1
    assert page.items[0].is_categorized is True
    compiled = compile_pg(executed_stmt(db))
    assert "LEFT OUTER JOIN incident_type_categories" in str(compiled)
    assert "ORDER BY count(*) DESC, log_entries.incident_type" in str(compiled)
    assert compiled.params["param_1"] == 100
    assert compiled.params["param_2"] == 100


def test_update_category_upserts_and_commits():
    db = MagicMock()
    update = CategoryUpdate(category="Traffic", normalized_type="Moving Violation")

    result = categories.update_category(db, "MV Stop", update)

    stmt = executed_stmt(db)
    assert "ON CONFLICT (raw_incident_type) DO UPDATE" in str(compile_pg(stmt))
    assert upsert_set_columns(stmt) == {
        "category",
        "normalized_type",
        "source",
        "needs_review",
        "prompt_version",
        "updated_at",
    }
    db.commit.assert_called_once()
    assert result.raw_incident_type == "MV Stop"
    assert result.category == "Traffic"
