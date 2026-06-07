from datetime import UTC, datetime

import logfire
import scrapy
from items.officer import OfficerItem
from scrapy.http import Request, Response

ROSTER_URL = "https://www.lebanonnh.gov/287/Divisions-Roster"


class OfficerRosterSpider(scrapy.Spider):
    name = "officer_roster"
    allowed_domains = ["www.lebanonnh.gov", "lebanonnh.gov"]

    async def start(self):
        yield Request(ROSTER_URL, callback=self.parse)

    def parse(self, response: Response, **kwargs):
        """Roster index — find links to division sub-pages."""
        division_links = response.css(".secondaryNav a[href^='/']")
        logfire.info("officer roster index", links=len(division_links))
        for link in division_links:
            href = link.attrib.get("href", "")
            if not href.startswith("/") or href == "/287/Divisions-Roster":
                continue
            division_name = link.css("::text").get("").strip()
            yield response.follow(
                href,
                callback=self.parse_division,
                cb_kwargs={"division": division_name},
            )

    def parse_division(self, response: Response, division: str = "", **kwargs):
        """Division page — extract officers from table rows or h-card widgets."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Try table-based layout first
        rows = response.css("#main-content table tbody tr")
        for row in rows:
            cells = [td.css("::text").get("").strip() for td in row.css("td")]
            if len(cells) < 2:
                continue
            rank, name = cells[0], cells[1]
            if not name:
                continue
            yield OfficerItem(
                name=name,
                rank=rank or None,
                division=division or None,
                phone=cells[2] if len(cells) > 2 else None,
                email=cells[3] if len(cells) > 3 else None,
                source_url=response.url,
                scraped_at=now,
            )

        # Fall back to h-card widget layout (real Department Roster page)
        if not rows:
            cards = response.css(".widgetItem.h-card")
            for card in cards:
                name = card.css(".p-name::text").get("").strip()
                rank = card.css(".p-job-title::text").get("").strip()
                email_href = card.css(".u-email a::attr(href)").get("")
                email = (
                    email_href.replace("mailto:", "").strip() if email_href else None
                )
                phone_href = card.css(".p-tel a::attr(href)").get("")
                phone = phone_href.replace("tel:", "").strip() if phone_href else None
                if not name:
                    continue
                yield OfficerItem(
                    name=name,
                    rank=rank or None,
                    division=division or None,
                    phone=phone,
                    email=email,
                    source_url=response.url,
                    scraped_at=now,
                )

        logfire.info("parsed officer division", division=division, url=response.url)
