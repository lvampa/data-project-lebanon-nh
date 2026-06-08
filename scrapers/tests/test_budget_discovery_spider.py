import pytest
from scrapy.http import HtmlResponse

from items.budget import BudgetDocumentItem
from spiders.budget_discovery import BudgetDiscoverySpider

INDEX_HTML = b"""
<html><body>
<div id="main-content">
  <a href="/1924/2026-Approved-City-Budget">2026 Approved City Budget</a>
  <a href="/1800/2025-Approved-City-Budget">2025 Approved City Budget</a>
  <a href="/852/Approved-City-Budgets">Back</a>
</div>
</body></html>
"""

YEAR_PAGE_HTML = b"""
<html><body>
<div id="main-content">
  <h1>2026 Approved City Budget</h1>
  <a href="/DocumentCenter/View/22618/2026-Budget-Book-PDF">Download Budget Book (PDF)</a>
  <a href="/DocumentCenter/View/22234/2026-Line-Item-Budget">Download Line Item Budget (PDF)</a>
  <a href="https://openGov.com/viewer">View Online Budget</a>
</div>
</body></html>
"""


@pytest.fixture
def spider():
    return BudgetDiscoverySpider()


def test_parse_index_follows_year_links(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/852/Approved-City-Budgets",
        body=INDEX_HTML,
    )
    results = list(spider.parse(response))
    urls = [r.url for r in results]
    assert any("2026" in u for u in urls)
    assert any("2025" in u for u in urls)
    assert not any("852" in u for u in urls), "should not follow link back to index"


def test_parse_year_page_yields_items(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/1924/2026-Approved-City-Budget",
        body=YEAR_PAGE_HTML,
    )
    results = list(spider.parse_year_page(response))
    assert len(results) == 2
    assert all(isinstance(r, BudgetDocumentItem) for r in results)


def test_parse_year_page_extracts_fiscal_year(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/1924/2026-Approved-City-Budget",
        body=YEAR_PAGE_HTML,
    )
    items = list(spider.parse_year_page(response))
    assert all(item["fiscal_year"] == 2026 for item in items)


def test_parse_year_page_classifies_document_types(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/1924/2026-Approved-City-Budget",
        body=YEAR_PAGE_HTML,
    )
    items = list(spider.parse_year_page(response))
    types = {item["document_type"] for item in items}
    assert "budget_book" in types
    assert "line_items" in types


def test_parse_year_page_skips_non_document_center_links(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/1924/2026-Approved-City-Budget",
        body=YEAR_PAGE_HTML,
    )
    items = list(spider.parse_year_page(response))
    assert all("DocumentCenter" in item["source_url"] for item in items)
