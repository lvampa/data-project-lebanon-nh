from datetime import date
from unittest.mock import MagicMock

from api.deps import Paging
from api.services import incidents
from api.tests.sql import compile_pg


def _list(**filters):
    db = MagicMock()
    db.scalar.return_value = 0
    db.scalars.return_value.all.return_value = []
    page = incidents.list_incidents(db, Paging(page=2, per_page=10), **filters)
    return page, compile_pg(db.scalars.call_args.args[0])


def test_list_incidents_skips_parse_errors_and_orders_stably():
    page, compiled = _list()

    assert (page.total, page.page, page.per_page) == (0, 2, 10)
    sql = str(compiled)
    assert "log_entries.parse_error = false" in sql
    assert (
        "ORDER BY log_entries.reported_at DESC NULLS LAST, log_entries.id DESC" in sql
    )
    assert compiled.params["param_1"] == 10
    assert compiled.params["param_2"] == 10


def test_list_incidents_date_to_includes_the_whole_day():
    _, compiled = _list(date_from=date(2026, 5, 1), date_to=date(2026, 5, 31))

    assert date(2026, 5, 1) in compiled.params.values()
    assert date(2026, 6, 1) in compiled.params.values()


def test_list_incidents_text_filters_escape_wildcards():
    _, compiled = _list(incident_type="50%_off", disposition="a", officer="b")

    assert str(compiled).count("ESCAPE '/'") == 3
    assert "50/%/_off" in compiled.params.values()
