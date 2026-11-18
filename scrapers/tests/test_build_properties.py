from datetime import UTC, datetime
from pathlib import Path

import pytest
from ingest import property_checks as checks
from maintenance.build_properties import main
from mongo.archive import ArchivedResponse, RawArchive
from postgres.models.crawl_run import CrawlRun
from postgres.models.property import Property
from postgres.models.property_sale import PropertySale
from sqlalchemy import select

PARCEL_HTML = (
    Path(__file__).parent / "fixtures" / "vgsi" / "parcel_business.html"
).read_bytes()
RUN_STARTED = datetime(2026, 11, 1)
SEEN = datetime(2026, 11, 2, tzinfo=UTC)


def archive_parcel(
    raw_sources, pid: str, body: bytes = PARCEL_HTML, seen: datetime = SEEN
) -> None:
    archive = RawArchive(raw_sources)
    archive.add(
        "vgsi_parcel",
        pid,
        ArchivedResponse(
            url=f"https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid={pid}",
            status=200,
            content_type="text/html",
            body=body,
            fetched_at=seen,
            spider="vgsi_property",
        ),
    )
    archive.flush()


def add_run(db_session, finished: bool = True) -> CrawlRun:
    run = CrawlRun(
        source="vgsi_property",
        started_at=RUN_STARTED,
        finished_at=datetime(2026, 11, 3) if finished else None,
        pages=2,
    )
    db_session.add(run)
    db_session.flush()
    return run


@pytest.fixture
def small_town(monkeypatch):
    monkeypatch.setattr(checks, "FIRST_BUILD_FLOOR", 1)


def test_a_build_stores_the_newest_page_of_each_parcel_with_its_lineage(
    db_session, raw_sources, small_town, capsys
):
    run = add_run(db_session)
    archive_parcel(raw_sources, "1949")

    assert main([]) == 0

    row = db_session.scalars(select(Property)).one()
    assert (row.mblu, row.vgsi_pid, row.owner) == (
        "91/264///",
        "1949",
        "ONE MECHANIC STREET LLC",
    )
    assert (row.crawl_run_id, row.fetched_at) == (run.id, SEEN.replace(tzinfo=None))
    sales = db_session.scalars(select(PropertySale)).all()
    assert len(sales) == 4
    assert {sale.property_id for sale in sales} == {row.id}
    assert "Built 1 parcels and 4 sales" in capsys.readouterr().out


def test_a_parcel_the_latest_run_did_not_see_is_dropped(
    db_session, raw_sources, small_town
):
    add_run(db_session)
    archive_parcel(raw_sources, "1949")
    # Another parcel last seen before the run began, and with a key of its own.
    archive_parcel(
        raw_sources,
        "2000",
        PARCEL_HTML.replace(b"264/", b"265/"),
        seen=datetime(2026, 10, 1, tzinfo=UTC),
    )

    assert main([]) == 0

    assert db_session.scalars(select(Property.vgsi_pid)).all() == ["1949"]


def test_a_failed_check_writes_nothing_and_exits_one(
    db_session, raw_sources, small_town, capsys
):
    run = add_run(db_session)
    kept = Property(
        mblu="1/1///",
        vgsi_pid="1",
        crawl_run_id=run.id,
        fetched_at=RUN_STARTED,
    )
    db_session.add(kept)
    db_session.flush()
    # Two pages with one key.
    archive_parcel(raw_sources, "1949")
    archive_parcel(raw_sources, "2000")

    assert main([]) == 1

    assert db_session.scalars(select(Property.vgsi_pid)).all() == ["1"]
    out = capsys.readouterr().out
    assert "FAIL key" in out
    assert "The tables still hold 1 parcels" in out


def test_a_crawl_that_did_not_finish_is_ignored(db_session, raw_sources, small_town):
    add_run(db_session, finished=False)
    archive_parcel(raw_sources, "1949")

    assert main([]) == 1

    assert db_session.scalars(select(Property)).all() == []
