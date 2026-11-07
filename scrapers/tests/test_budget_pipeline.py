from datetime import datetime
from unittest.mock import MagicMock

import pytest
from items.budget import BudgetDocumentItem
from pipelines import BudgetDocumentPipeline

SAMPLE_ITEM = BudgetDocumentItem(
    fiscal_year=2026,
    document_type="budget_book",
    source_url="https://www.lebanonnh.gov/DocumentCenter/View/22618",
    scraped_at=datetime(2026, 6, 7, 12, 0, 0),
)


@pytest.fixture
def pipeline():
    pl = BudgetDocumentPipeline()
    pl._session = MagicMock()
    return pl


def test_ignores_non_budget_items(pipeline):
    from items.officer import OfficerItem

    other = OfficerItem(
        name="Jane Doe",
        source_url="http://x",
        scraped_at=datetime.now(),
    )
    result = pipeline.process_item(other)
    assert result is other
    pipeline._session.execute.assert_not_called()


def test_upserts_budget_document(pipeline):
    pipeline.process_item(SAMPLE_ITEM)
    pipeline._session.execute.assert_called_once()


def test_close_spider_closes_session(pipeline):
    pipeline.close_spider()
    pipeline._session.close.assert_called_once()


def test_first_item_stays_committed_when_second_fails(fake_session):
    pipeline = BudgetDocumentPipeline()
    pipeline._session = fake_session
    fake_session.fail_on_call = 2

    pipeline.process_item(SAMPLE_ITEM)
    with pytest.raises(RuntimeError):
        pipeline.process_item(SAMPLE_ITEM)
    pipeline.close_spider()

    assert len(fake_session.committed) == 1
