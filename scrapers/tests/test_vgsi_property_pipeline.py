from datetime import datetime
from unittest.mock import MagicMock

import pytest
from items.property import PropertyItem
from pipelines import PropertyPipeline
from postgres.models.property import Property
from postgres.models.property_sale import PropertySale
from sqlalchemy import select

SAMPLE_ITEM = PropertyItem(
    parcel_id="10001",
    location="123 ABBOTT ST",
    owner="SMITH, JOHN",
    owner_address="PO BOX 1, LEBANON NH 03766",
    land_use="101 - Res 1 Family",
    assessed_land=100000,
    assessed_building=250000,
    assessed_total=350000,
    lot_size_acres=0.25,
    year_built=1985,
    building_sqft=1450,
    assessment_year=None,
    detail_url="https://gis.vgsi.com/LebanonNH/Parcel.aspx?Pid=10001",
    sales=[
        {
            "sale_date": "01/15/2019",
            "sale_price": 320000,
            "grantee": "SMITH, JOHN",
            "grantor": "JONES, BOB",
        }
    ],
)


@pytest.fixture
def pipeline():
    pl = PropertyPipeline()
    pl._session = MagicMock()
    # Mock the property_id lookup after upsert
    pl._session.execute.return_value.scalar_one.return_value = 42
    return pl


def test_ignores_non_property_items(pipeline):
    from items.police_log import PoliceLogItem

    other = PoliceLogItem(
        raw_text="x", source_url="http://x", scraped_at=datetime.now()
    )
    result = pipeline.process_item(other, MagicMock())
    assert result is other


def test_process_item_returns_item(pipeline):
    result = pipeline.process_item(SAMPLE_ITEM, MagicMock())
    assert result is SAMPLE_ITEM


def test_upserts_property(pipeline):
    pipeline.process_item(SAMPLE_ITEM, MagicMock())
    assert pipeline._session.execute.called


def test_inserts_sale_after_delete(pipeline):
    pipeline.process_item(SAMPLE_ITEM, MagicMock())
    # Multiple execute calls: upsert + id lookup + delete + sale insert
    assert pipeline._session.execute.call_count >= 3


def test_parses_sale_date(pipeline):
    """Sale date '01/15/2019' must not cause an exception."""
    pipeline.process_item(SAMPLE_ITEM, MagicMock())


def test_close_spider_closes_session(pipeline):
    pipeline.close_spider(MagicMock())
    pipeline._session.close.assert_called_once()


def test_first_property_stays_committed_when_second_fails(db_session, fail_on_execute):
    pipeline = PropertyPipeline()
    pipeline.open_spider(None)
    # SAMPLE_ITEM runs upsert, id lookup, sales delete, one sale insert.
    # Failing on call 8 breaks the second run's sale insert, after its delete.
    fail_on_execute(pipeline._session, 8)
    rescrape = PropertyItem(SAMPLE_ITEM, owner="NEW OWNER")

    pipeline.process_item(SAMPLE_ITEM, None)
    with pytest.raises(RuntimeError):
        pipeline.process_item(rescrape, None)
    pipeline.close_spider(None)

    # The failed rescrape is rolled back whole: the owner and the sale are the first run's.
    assert db_session.scalars(select(Property.owner)).all() == ["SMITH, JOHN"]
    assert db_session.scalars(select(PropertySale.grantor)).all() == ["JONES, BOB"]
