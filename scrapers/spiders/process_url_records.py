from datetime import datetime, timezone
from typing import Any

import logfire
import scrapy
from scrapy.http import Request, Response

from mongo import db
from items import DownloadedUrlItem
from models import UrlDocument


class ProcessUrlsSpider(scrapy.Spider):
    name = "process_urls"

    def __init__(self, limit: int = 10, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.limit: int = int(limit)

    async def start(self):
        urls = db.get_collection("urls")
        pending = list(urls.find({"state": "pending"}).limit(self.limit))

        logfire.info("queued urls for download", count=len(pending), limit=self.limit)

        for doc in pending:
            url_doc = UrlDocument(**doc)
            yield Request(url_doc.canonical_url, cb_kwargs={"url_doc": url_doc})

    def parse(self, response: Response, url_doc: UrlDocument, **kwargs: Any) -> Any:
        with logfire.span("download pdf", url=response.url):
            if not response.body.startswith(b"%PDF"):
                logfire.warning("response is not a pdf", url=response.url)
                item = DownloadedUrlItem(url_doc_id=url_doc.id, state="error")
            else:
                logfire.info(
                    "pdf downloaded",
                    url=response.url,
                    size_bytes=len(response.body),
                )
                item = DownloadedUrlItem(
                    url_doc_id=url_doc.id,
                    state="downloaded",
                    pdf_data=response.body,
                    downloaded_at=datetime.now(timezone.utc),
                )

        yield item
