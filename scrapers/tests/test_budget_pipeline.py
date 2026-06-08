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
    result = pipeline.process_item(other, MagicMock())
    assert result is other
    pipeline._session.execute.assert_not_called()


def test_upserts_budget_document(pipeline):
    pipeline.process_item(SAMPLE_ITEM, MagicMock())
    pipeline._session.execute.assert_called_once()


def test_close_commits(pipeline):
    pipeline.close_spider(MagicMock())
    pipeline._session.commit.assert_called_once()
    pipeline._session.close.assert_called_once()
