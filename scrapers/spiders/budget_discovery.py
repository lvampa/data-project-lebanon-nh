import re
from datetime import UTC, datetime

import logfire
import scrapy
from items.budget import BudgetDocumentItem
from scrapy.http import Request, Response

INDEX_URL = "https://www.lebanonnh.gov/852/Approved-City-Budgets"

DOCUMENT_TYPE_PATTERNS = [
    (re.compile(r"line.?item", re.IGNORECASE), "line_items"),
    (re.compile(r"budget", re.IGNORECASE), "budget_book"),
]


def _classify_document_type(link_text: str) -> str | None:
    for pattern, doc_type in DOCUMENT_TYPE_PATTERNS:
        if pattern.search(link_text):
            return doc_type
    return None


def _extract_fiscal_year(url: str) -> int | None:
    match = re.search(r"/(20\d{2})[/-]", url)
    return int(match.group(1)) if match else None


class BudgetDiscoverySpider(scrapy.Spider):
    name = "budget_discovery"
    allowed_domains = ["www.lebanonnh.gov", "lebanonnh.gov"]

    def start_requests(self):
        yield Request(INDEX_URL, callback=self.parse)

    def parse(self, response: Response, **kwargs):
        """Index page — follow links to individual year budget pages."""
        links = response.css(
            "#main-content a[href*='Budget'], .field-items a[href*='Budget']"
        )
        logfire.info("budget index", links=len(links))
        seen = set()
        for link in links:
            href = link.attrib.get("href", "")
            if not href or href in seen:
                continue
            # Skip the index page itself
            if "/852/" in href:
                continue
            seen.add(href)
            yield response.follow(href, callback=self.parse_year_page)

    def parse_year_page(self, response: Response, **kwargs):
        """Year sub-page — extract PDF download links."""
        now = datetime.now(UTC).replace(tzinfo=None)
        fiscal_year = _extract_fiscal_year(response.url)
        if not fiscal_year:
            logfire.warning("could not extract fiscal year", url=response.url)
            return

        for link in response.css("a[href*='DocumentCenter']"):
            href = link.attrib.get("href", "")
            if not href:
                continue
            text = link.css("::text").get("").strip()
            doc_type = _classify_document_type(text)
            if not doc_type:
                continue
            yield BudgetDocumentItem(
                fiscal_year=fiscal_year,
                document_type=doc_type,
                source_url=response.urljoin(href),
                scraped_at=now,
            )

        logfire.info(
            "parsed budget year page", fiscal_year=fiscal_year, url=response.url
        )
