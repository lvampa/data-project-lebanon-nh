from typing import Any, Self
from urllib.parse import urljoin

import logfire
import scrapy
from crawl_runs import finish_run, start_run
from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.http import Request, Response

BASE_URL = "https://gis.vgsi.com/LebanonNH/"
# Streets.aspx lists the A streets, so the link to letter A would fetch the same page.
FIRST_LETTER_HREF = "Streets.aspx?Letter=A"


def _parcel_id(url: str) -> str:
    return url.split("pid=")[-1].split("&")[0]


class VgsiPropertySpider(scrapy.Spider):
    """Fetches every parcel page and parses nothing.

    The raw archive middleware stores each page. `uv run build-properties` parses the
    archive, so a parser fix never needs a recrawl.
    """

    name = "vgsi_property"
    allowed_domains = ["gis.vgsi.com"]
    archive_source = "vgsi_parcel"
    pages = 0
    run_id: int | None = None

    @classmethod
    def from_crawler(cls, crawler: Crawler, *args: Any, **kwargs: Any) -> Self:
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.open_run, signal=signals.spider_opened)
        crawler.signals.connect(spider.close_run, signal=signals.spider_closed)
        return spider

    def open_run(self) -> None:
        self.run_id = start_run(self.name)

    def close_run(self, reason: str) -> None:
        # Only a crawl that ran to the end counts. A stopped one stays unfinished.
        if reason == "finished" and self.run_id is not None:
            finish_run(self.run_id, self.pages)

    def archive_key(self, response: Response) -> str | None:
        # Street index pages only list parcels; the parcel pages are the originals.
        if "Parcel.aspx" not in response.url:
            return None
        return _parcel_id(response.url)

    async def start(self):
        yield Request(urljoin(BASE_URL, "Streets.aspx"), callback=self.parse)

    def parse(self, response: Response, **kwargs):
        # An index page lists one letter's streets and links to the other letters.
        # The dupe filter stops the letters from following each other round.
        links = response.css("a[href*='Streets.aspx?Name=']")
        logfire.info("vgsi streets index", count=len(links))
        for link in links:
            yield Request(
                urljoin(BASE_URL, link.attrib["href"]),
                callback=self.parse_street,
            )
        for link in response.css("a[href*='Streets.aspx?Letter=']"):
            if link.attrib["href"] != FIRST_LETTER_HREF:
                yield Request(
                    urljoin(BASE_URL, link.attrib["href"]), callback=self.parse
                )

    def parse_street(self, response: Response, **kwargs):
        for link in response.css("a[href*='Parcel.aspx?pid=']"):
            yield Request(
                urljoin(BASE_URL, link.attrib["href"]),
                callback=self.parse_parcel,
            )

    def parse_parcel(self, response: Response, **kwargs) -> None:
        self.pages += 1
