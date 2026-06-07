from datetime import datetime
from unittest.mock import MagicMock

import pytest
from items.city_staff import CityStaffItem
from pipelines import CityStaffPipeline

SAMPLE_ITEM = CityStaffItem(
    name="Jane Doe",
    title="Patrol Officer",
    department="Police",
    division="Patrol Division",
    email="jdoe@police.nh.gov",
    phone="(603) 448-1234",
    source_url="https://www.lebanonnh.gov/796/Department-Roster",
    scraped_at=datetime(2026, 6, 3, 12, 0, 0),
)


@pytest.fixture
def pipeline():
    pl = CityStaffPipeline()
    pl._session = MagicMock()
    return pl


def test_ignores_non_city_staff_items(pipeline):
    from items.police_log import PoliceLogItem

    other = PoliceLogItem(
        raw_text="x", source_url="http://x", scraped_at=datetime.now()
    )
    result = pipeline.process_item(other, MagicMock())
    assert result is other
    pipeline._session.execute.assert_not_called()


def test_upserts_city_staff(pipeline):
    pipeline.process_item(SAMPLE_ITEM, MagicMock())
    pipeline._session.execute.assert_called_once()


def test_process_item_returns_item(pipeline):
    result = pipeline.process_item(SAMPLE_ITEM, MagicMock())
    assert result is SAMPLE_ITEM


def test_close_commits(pipeline):
    pipeline.close_spider(MagicMock())
    pipeline._session.commit.assert_called_once()
    pipeline._session.close.assert_called_once()
