from unittest.mock import MagicMock

from postgres.models.llc import Llc as LlcModel

from api.deps import Paging
from api.services import llcs
from api.tests.sql import compile_pg


def test_list_llcs_filters_by_status_and_orders_by_name():
    db = MagicMock()
    db.scalar.return_value = 0
    db.scalars.return_value.all.return_value = []

    page = llcs.list_llcs(db, Paging(page=2, per_page=10), lookup_status="pending")

    assert (page.total, page.page, page.per_page) == (0, 2, 10)
    compiled = compile_pg(db.scalars.call_args.args[0])
    assert "WHERE llcs.lookup_status = %(lookup_status_1)s" in str(compiled)
    assert "ORDER BY llcs.name" in str(compiled)
    assert compiled.params["lookup_status_1"] == "pending"


def test_update_llc_status_sets_status_and_commits():
    db = MagicMock()
    row = LlcModel(id=1, name="X LLC", lookup_status="pending")
    db.get.return_value = row

    result = llcs.update_llc_status(db, 1, "complete")

    assert result is row
    assert row.lookup_status == "complete"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(row)


def test_update_llc_status_returns_none_for_unknown_id():
    db = MagicMock()
    db.get.return_value = None

    assert llcs.update_llc_status(db, 999, "complete") is None
    db.commit.assert_not_called()
