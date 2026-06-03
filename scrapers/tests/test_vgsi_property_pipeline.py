from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pytest

from items.property import PropertyItem
from pipelines import PropertyPipeline


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
    other = PoliceLogItem(raw_text="x", source_url="http://x", scraped_at=datetime.now())
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


def test_close_spider_commits(pipeline):
    pipeline.close_spider(MagicMock())
    pipeline._session.commit.assert_called_once()
    pipeline._session.close.assert_called_once()
