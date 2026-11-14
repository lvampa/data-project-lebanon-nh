import logfire
from scrapy import Item, Spider, signals
from scrapy.crawler import Crawler
from scrapy.http import Response
from scrapy.statscollectors import StatsCollector
from twisted.python.failure import Failure


class LogfireExtension:
    """Scrapy extension that configures Logfire and tracks spider lifecycle."""

    def __init__(self, stats: StatsCollector) -> None:
        self.stats = stats
        logfire.configure()
        logfire.instrument_pymongo()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "LogfireExtension":
        ext = cls(crawler.stats)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(ext.item_error, signal=signals.item_error)
        crawler.signals.connect(ext.spider_error, signal=signals.spider_error)
        return ext

    def spider_opened(self, spider: Spider) -> None:
        logfire.info("spider started", spider=spider.name)

    def spider_closed(self, spider: Spider, reason: str) -> None:
        stats = self.stats.get_stats(spider)
        logfire.info(
            "spider closed",
            spider=spider.name,
            reason=reason,
            item_count=stats.get("item_scraped_count", 0),
            request_count=stats.get("downloader/request_count", 0),
            response_count=stats.get("downloader/response_count", 0),
            error_count=stats.get("log_count/ERROR", 0),
        )

    def item_error(
        self, item: Item, response: Response | None, spider: Spider, failure: Failure
    ) -> None:
        logfire.error(
            "item pipeline error",
            spider=spider.name,
            url=response.url if response else None,
            error=str(failure),
        )

    def spider_error(
        self, failure: Failure, response: Response | None, spider: Spider
    ) -> None:
        logfire.error(
            "spider error",
            spider=spider.name,
            url=response.url if response else None,
            error=str(failure),
        )
