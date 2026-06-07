import re
from collections.abc import Generator
from datetime import datetime, timezone

import logfire
import scrapy
from scrapy.http import Request, Response

from items.city_staff import CityStaffItem

DEPT_ROSTER_SOURCES = [
    ("https://www.lebanonnh.gov/796/Department-Roster", "Police"),
    ("https://www.lebanonnh.gov/1718/Department-Roster", "Fire"),
]

DIRECTORY_SOURCES = [
    ("https://www.lebanonnh.gov/Directory.aspx?did=37", "Clerk"),
    ("https://flyleb.com/directory.aspx?did=6", "Airport"),
]

COUNCIL_INDEX_URL = "https://www.lebanonnh.gov/337/City-Council"


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    val = text.strip()
    return val if val else None


class CityStaffSpider(scrapy.Spider):
    name = "city_staff"
    allowed_domains = ["www.lebanonnh.gov", "lebanonnh.gov", "flyleb.com"]

    def start_requests(self) -> Generator[Request, None, None]:
        for url, dept in DEPT_ROSTER_SOURCES:
            yield Request(url, callback=self.parse_dept_roster, cb_kwargs={"department": dept})
        for url, dept in DIRECTORY_SOURCES:
            yield Request(url, callback=self.parse_directory_table, cb_kwargs={"department": dept})
        yield Request(COUNCIL_INDEX_URL, callback=self.parse_council_index)

    def parse_dept_roster(self, response: Response, department: str = "", **kwargs) -> Generator[CityStaffItem, None, None]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        current_division: str | None = None
        items: list[CityStaffItem] = []

        for el in response.css("h2, h3, dl"):
            tag = el.root.tag if hasattr(el, "root") else el.xpath("name()").get("")
            if tag in ("h2", "h3"):
                heading = _clean(el.css("::text").get())
                if heading:
                    current_division = heading
                continue

            dd = el.css("dd")
            if not dd:
                continue

            texts = [_clean(t) for t in dd.css("::text").getall() if _clean(t)]
            if not texts:
                continue

            name = texts[0]
            title = texts[1] if len(texts) > 1 else None
            rest = texts[2:]
            email = next((t for t in rest if "@" in t), None)
            phone = next(
                (t for t in rest if re.match(r"\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}", t)),
                None,
            )

            if not name:
                continue

            items.append(CityStaffItem(
                name=name,
                title=title,
                department=department,
                division=current_division,
                email=email,
                phone=phone,
                source_url=response.url,
                scraped_at=now,
            ))

        logfire.info("parsed dept roster", department=department, count=len(items), url=response.url)
        yield from items

    def parse_directory_table(self, response: Response, department: str = "", **kwargs) -> Generator[CityStaffItem, None, None]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        items: list[CityStaffItem] = []

        for row in response.css("table tbody tr"):
            cells = [_clean(td.css("::text").get()) for td in row.css("td")]
            if len(cells) < 2 or not cells[0]:
                continue

            items.append(CityStaffItem(
                name=cells[0],
                title=cells[1] if len(cells) > 1 else None,
                department=department,
                division=None,
                email=cells[2] if len(cells) > 2 else None,
                phone=cells[3] if len(cells) > 3 else None,
                source_url=response.url,
                scraped_at=now,
            ))

        logfire.info("parsed directory table", department=department, count=len(items), url=response.url)
        yield from items

    def parse_council_index(self, response: Response, **kwargs) -> Generator[Request, None, None]:
        links = response.css("a[href*='/Councilor-']")
        logfire.info("city council index", links=len(links))
        seen = set()
        for link in links:
            href = link.attrib.get("href", "")
            if href and href not in seen:
                seen.add(href)
                yield response.follow(href, callback=self.parse_council_member)

    def parse_council_member(self, response: Response, **kwargs) -> Generator[CityStaffItem, None, None]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        page_title = _clean(response.css("title::text").get() or "")
        name = page_title.split("|")[0].replace("Councilor", "").strip() if page_title else None

        title = _clean(response.css("h2.page-title + p::text, .page-description::text").get())

        if not title:
            for p in response.css("#main-content p, .fr-view p"):
                text = _clean(p.css("::text").get())
                if text and ("Councilor" in text or "Mayor" in text):
                    title = text
                    break

        email_href = response.css("a[href^='mailto:']::attr(href)").get()
        email = email_href.replace("mailto:", "").strip() if email_href else None

        if not name:
            return

        logfire.info("parsed councilor", name=name, url=response.url)
        yield CityStaffItem(
            name=name,
            title=title,
            department="City Council",
            division=None,
            email=email,
            phone=None,
            source_url=response.url,
            scraped_at=now,
        )
