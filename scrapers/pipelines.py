import logfire
import scrapy
from pymongo import UpdateOne

from mongo import db
from items import DownloadedUrlItem, PoliceLogItem, UrlRecordItem


class UrlRecordPipeline:
    def open_spider(self, spider) -> None:
        self._ops: list[UpdateOne] = []
        self._count: int = 0

    def process_item(self, item: scrapy.Item, spider: scrapy.Spider) -> scrapy.Item:
        if not isinstance(item, UrlRecordItem):
            return item

        self._count += 1
        self._ops.append(
            UpdateOne(
                {"canonical_url": item["canonical_url"]},
                {"$setOnInsert": {
                    "canonical_url": item["canonical_url"],
                    "archive_url": item.get("archive_url"),
                    "state": item["state"],
                    "created_at": item["created_at"],
                }},
                upsert=True,
            )
        )
        return item

    def close_spider(self, spider) -> None:
        if not self._ops:
            return

        with logfire.span("bulk upsert url records", found=self._count, count=len(self._ops)):
            result = db.get_collection("urls").bulk_write(self._ops, ordered=False)
            logfire.info(
                "url records flushed",
                found=self._count,
                inserted=result.upserted_count,
                matched=result.matched_count,
            )


class UrlDownloadPipeline:
    def process_item(self, item: scrapy.Item, spider: scrapy.Spider) -> scrapy.Item:
        if not isinstance(item, DownloadedUrlItem):
            return item

        with logfire.span("save download result", url_doc_id=str(item["url_doc_id"]), state=item["state"]):
            update = {"state": item["state"]}
            if "pdf_data" in item:
                update["pdf_data"] = item["pdf_data"]
            if "downloaded_at" in item:
                update["downloaded_at"] = item["downloaded_at"]

            db.get_collection("urls").update_one(
                {"_id": item["url_doc_id"]},
                {"$set": update},
            )

        return item


class PoliceLogPipeline:
    def process_item(self, item: scrapy.Item, spider: scrapy.Spider) -> scrapy.Item:
        if not isinstance(item, PoliceLogItem):
            return item

        with logfire.span("save police log", source_url=item["source_url"]):
            db.get_collection("police_logs").update_one(
                {"source_url": item["source_url"]},
                {"$set": dict(item)},
                upsert=True,
            )

        return item
