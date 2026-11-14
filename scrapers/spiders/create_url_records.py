import re
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any, cast, override
from urllib.parse import urljoin, urlparse, urlunparse

from items import UrlRecordItem
from scrapy.http import Request, Response
from scrapy.selector import Selector
from scrapy.spiders import Spider

_ARCHIVE_RE = re.compile(r"https://web\.archive\.org/web/\d+[a-z]*/(.+)")
_LOG_DATE_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})(?:[/?#]|$)")


class BuildDailyUrlsSpider(Spider):
    name = "build_daily_urls"

    def __init__(
        self,
        url: str = "https://www.lebanonnh.gov/232/Daily-Police-Log",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.url = url

    @override
    async def start(self) -> AsyncIterator[Request]:
        yield Request(self.url, callback=self.parse_index)

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

    def parse_index(self, response: Response, **kwargs: Any) -> Iterator[UrlRecordItem]:
        # pdf_urls.created_at is a naive column that holds UTC, like the other writers.
        now = datetime.now(UTC).replace(tzinfo=None)
        for link in cast(list[Selector], response.css("a.fileType.pdf")):
            result = self.extract_url(link, response.url)
            if not result:
                continue
            canonical_url, archive_url = result
            date_match = _LOG_DATE_RE.search(canonical_url)
            log_date = (
                datetime.strptime(date_match.group(1), "%Y-%m-%d")
                if date_match
                else None
            )
            yield UrlRecordItem(
                canonical_url=canonical_url,
                archive_url=archive_url,
                log_date=log_date,
                state="pending",
                created_at=now,
            )
