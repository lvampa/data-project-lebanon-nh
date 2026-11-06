from datetime import datetime
from unittest.mock import MagicMock

import pytest
from items.officer import OfficerItem
from pipelines import OfficerPipeline
from postgres.models.officer import Officer
from sqlalchemy import select

SAMPLE_ITEM = OfficerItem(
    name="John Smith",
    rank="Chief",
    division="Patrol",
    phone="(603) 448-1212",
    email="jsmith@lebanonnh.gov",
    source_url="https://www.lebanonnh.gov/290/Patrol-Division",
    scraped_at=datetime(2026, 6, 3, 12, 0, 0),
)


@pytest.fixture
def pipeline():
    pl = OfficerPipeline()
    pl._session = MagicMock()
    return pl


def test_ignores_non_officer_items(pipeline):
    from items.police_log import PoliceLogItem

    other = PoliceLogItem(
        raw_text="x", source_url="http://x", scraped_at=datetime.now()
    )
    result = pipeline.process_item(other, MagicMock())
    assert result is other
    pipeline._session.execute.assert_not_called()


def test_upserts_officer(pipeline):
    pipeline.process_item(SAMPLE_ITEM, MagicMock())
    pipeline._session.execute.assert_called_once()


def test_close_spider_closes_session(pipeline):
    pipeline.close_spider(MagicMock())
    pipeline._session.close.assert_called_once()


def test_first_item_stays_committed_when_second_fails(db_session, fail_on_execute):
    pipeline = OfficerPipeline()
    pipeline.open_spider(None)
    fail_on_execute(pipeline._session, 2)
    second = OfficerItem(SAMPLE_ITEM, name="Jane Doe")

    pipeline.process_item(SAMPLE_ITEM, None)
    with pytest.raises(RuntimeError):
        pipeline.process_item(second, None)
    pipeline.close_spider(None)

    assert db_session.scalars(select(Officer.name)).all() == ["John Smith"]
