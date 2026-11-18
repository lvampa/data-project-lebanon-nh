from datetime import datetime

from postgres.models.crawl_run import CrawlRun
from postgres.models.property import Property
from sqlalchemy import text

PUBLISHED = [
    "parcel_id",
    "location",
    "owner",
    "owner_address",
    "land_use",
    "lot_size_acres",
    "year_built",
    "building_sqft",
    "assessed_land",
    "assessed_building",
    "assessed_total",
    "assessment_year",
    "detail_url",
]


def test_the_export_view_lists_the_published_columns_and_names_the_key_parcel_id(
    db_session,
):
    run = CrawlRun(source="vgsi_property", started_at=datetime(2026, 11, 1))
    db_session.add(run)
    db_session.flush()
    db_session.add(
        Property(
            mblu="91/264///",
            vgsi_pid="1949",
            co_owner="NOT PUBLISHED",
            crawl_run_id=run.id,
            fetched_at=datetime(2026, 11, 2),
        )
    )
    db_session.flush()

    result = db_session.execute(text("SELECT * FROM public_properties"))

    assert list(result.keys()) == PUBLISHED
    assert result.one().parcel_id == "1949"
