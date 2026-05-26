import logfire
from pymongo import UpdateOne
from sqlalchemy.dialects.postgresql import insert as pg_insert

from items import PoliceLogItem, UrlRecordItem
from mongo import db
from postgres import SessionLocal
from postgres.models.log_entry import LogEntry


class UrlRecordPipeline:
    def open_spider(self, spider) -> None:
        self._ops: list[UpdateOne] = []
        self._count: int = 0

    def process_item(self, item, spider):
        if not isinstance(item, UrlRecordItem):
            return item

        self._count += 1
        self._ops.append(
            UpdateOne(
                {"canonical_url": item["canonical_url"]},
                {"$setOnInsert": {
                    "canonical_url": item["canonical_url"],
                    "archive_url": item.get("archive_url"),
                    "log_date": item.get("log_date"),
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


class PoliceLogPipeline:
    def open_spider(self, spider) -> None:
        self._session = SessionLocal()

    def process_item(self, item, spider):
        if not isinstance(item, PoliceLogItem):
            return item

        with logfire.span("save police log entry", source_url=item["source_url"]):
            stmt = pg_insert(LogEntry).values(
                source_url=item["source_url"],
                case_number=item.get("case_number"),
                reported_at=item.get("reported_at"),
                call_source=item.get("call_source"),
                incident_type=item.get("incident_type"),
                disposition=item.get("disposition"),
                raw_reason_action=item.get("raw_reason_action"),
                location=item.get("location"),
                officer=item.get("officer"),
                reference_number=item.get("reference_number"),
                dispatched_at=item.get("dispatched_at"),
                enroute_at=item.get("enroute_at"),
                arrived_at=item.get("arrived_at"),
                cleared_at=item.get("cleared_at"),
                response_seconds=item.get("response_seconds"),
                scene_seconds=item.get("scene_seconds"),
                raw_text=item["raw_text"],
                parse_error=item.get("parse_error", False),
                scraped_at=item["scraped_at"],
            ).on_conflict_do_nothing(index_elements=["case_number"])
            self._session.execute(stmt)

        return item

    def close_spider(self, spider) -> None:
        self._session.commit()
        self._session.close()
