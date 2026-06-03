import logfire
from datetime import date as _date, datetime, timezone
from pymongo import UpdateOne
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from items import PoliceLogItem, UrlRecordItem
from items.property import PropertyItem
from mongo import db
from postgres import SessionLocal
from postgres.models.log_entry import LogEntry
from postgres.models.property import Property
from postgres.models.property_sale import PropertySale


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


def _parse_sale_date(raw: str | None) -> _date | None:
    if not raw:
        return None
    try:
        m, d, y = raw.strip().split("/")
        return _date(int(y), int(m), int(d))
    except Exception:
        return None


class PropertyPipeline:
    def open_spider(self, spider) -> None:
        self._session = SessionLocal()

    def process_item(self, item, spider):
        if not isinstance(item, PropertyItem):
            return item

        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            parcel_id = item["parcel_id"]

            with logfire.span("save property", parcel_id=parcel_id):
                # Upsert property
                stmt = pg_insert(Property).values(
                    parcel_id=parcel_id,
                    location=item.get("location"),
                    owner=item.get("owner"),
                    owner_address=item.get("owner_address"),
                    land_use=item.get("land_use"),
                    lot_size_acres=item.get("lot_size_acres"),
                    year_built=item.get("year_built"),
                    building_sqft=item.get("building_sqft"),
                    assessed_land=item.get("assessed_land"),
                    assessed_building=item.get("assessed_building"),
                    assessed_total=item.get("assessed_total"),
                    assessment_year=item.get("assessment_year"),
                    detail_url=item.get("detail_url"),
                    created_at=now,
                    updated_at=now,
                ).on_conflict_do_update(
                    index_elements=["parcel_id"],
                    set_={
                        "location": item.get("location"),
                        "owner": item.get("owner"),
                        "owner_address": item.get("owner_address"),
                        "land_use": item.get("land_use"),
                        "lot_size_acres": item.get("lot_size_acres"),
                        "year_built": item.get("year_built"),
                        "building_sqft": item.get("building_sqft"),
                        "assessed_land": item.get("assessed_land"),
                        "assessed_building": item.get("assessed_building"),
                        "assessed_total": item.get("assessed_total"),
                        "assessment_year": item.get("assessment_year"),
                        "detail_url": item.get("detail_url"),
                        "updated_at": now,
                    },
                )
                self._session.execute(stmt)

                # Get the property PK to link sales
                property_id = self._session.execute(
                    select(Property.id).where(Property.parcel_id == parcel_id)
                ).scalar_one()

                # Replace sales
                self._session.execute(
                    delete(PropertySale).where(PropertySale.property_id == property_id)
                )
                for sale in item.get("sales") or []:
                    self._session.execute(
                        pg_insert(PropertySale).values(
                            property_id=property_id,
                            sale_date=_parse_sale_date(sale.get("sale_date")),
                            sale_price=sale.get("sale_price"),
                            grantee=sale.get("grantee"),
                            grantor=sale.get("grantor"),
                            created_at=now,
                        )
                    )
        except Exception:
            self._session.rollback()
            raise

        return item

    def close_spider(self, spider) -> None:
        self._session.commit()
        self._session.close()
