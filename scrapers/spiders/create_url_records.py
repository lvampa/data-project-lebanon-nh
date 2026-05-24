import re
from datetime import datetime, timezone
from typing import Any, cast
from urllib.parse import urljoin, urlparse, urlunparse

from scrapy.http import Request, TextResponse
from scrapy.selector import Selector
from scrapy.spiders import Spider

from items import UrlRecordItem

_ARCHIVE_RE = re.compile(r"https://web\.archive\.org/web/\d+[a-z]*/(.+)")


class BuildDailyUrlsSpider(Spider):
    name = "build_daily_urls"

    def __init__(self, url: str = "https://www.lebanonnh.gov/853/Daily-Log", *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.url = url

    async def start(self):
        yield Request(self.url)

    @staticmethod
    def extract_url(link: Selector, base_url: str) -> tuple[str, str | None] | None:
        href: str | None = link.css("::attr(href)").get()
        if not href:
            return None

        absolute = str(urljoin(base_url, href))
        parsed = urlparse(absolute)
        cleaned = str(urlunparse(parsed._replace(query="", fragment="")))

        match = _ARCHIVE_RE.match(cleaned)
        if match:
            raw = match.group(1)
            canonical = raw if raw.startswith("http") else f"https://{raw}"
            return canonical, cleaned

        return cleaned, None

    def parse(self, response: TextResponse, **kwargs: Any) -> Any:
        now = datetime.now(timezone.utc)
        for link in cast(list[Selector], response.css("a.fileType.pdf.docaccess-activated")):
            result = self.extract_url(link, response.url)
            if not result:
                continue
            canonical_url, archive_url = result
            yield UrlRecordItem(
                canonical_url=canonical_url,
                archive_url=archive_url,
                state="pending",
                created_at=now,
            )
