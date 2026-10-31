from unittest.mock import MagicMock

from api.services import stats
from api.tests.sql import compile_pg, executed_stmt


def _db(*rows):
    db = MagicMock()
    db.execute.return_value.all.return_value = [MagicMock(**r) for r in rows]
    return db


def test_by_type_returns_top_twenty_types():
    db = _db({"incident_type": "MV Stop", "count": 8})

    result = stats.by_type(db)

    assert [(r.incident_type, r.count) for r in result] == [("MV Stop", 8)]
    compiled = compile_pg(executed_stmt(db))
    assert "GROUP BY log_entries.incident_type" in str(compiled)
    assert "ORDER BY count(*) DESC" in str(compiled)
    assert compiled.params["param_1"] == 20


def test_by_hour_buckets_on_reported_hour():
    db = _db({"hour": 14.0, "count": 3})

    result = stats.by_hour(db)

    assert [(r.hour, r.count) for r in result] == [(14, 3)]
    assert "EXTRACT(hour FROM log_entries.reported_at)" in str(
        compile_pg(executed_stmt(db))
    )


def test_by_weekday_names_days_from_sunday():
    db = _db({"dow": 0, "count": 5}, {"dow": 6, "count": 2})

    result = stats.by_weekday(db)

    assert [(r.day, r.count) for r in result] == [("Sun", 5), ("Sat", 2)]
    assert "EXTRACT(dow FROM log_entries.reported_at)" in str(
        compile_pg(executed_stmt(db))
    )
