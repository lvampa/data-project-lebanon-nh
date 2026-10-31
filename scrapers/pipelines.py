import re
from datetime import UTC, datetime

import logfire
from items import PoliceLogPdfItem, UrlRecordItem
from items.budget import BudgetDocumentItem
from items.city_staff import CityStaffItem
from items.officer import OfficerItem
from items.property import PropertyItem
from models.budget_document import BudgetDocumentRecord
from models.city_staff import CityStaffRecord
from models.officer import OfficerRecord
from models.police_log import PoliceLogRecord
from models.property import PropertyRecord
from models.url_record import UrlRecord
from postgres import SessionLocal
from postgres.models.budget_document import BudgetDocument
from postgres.models.city_staff import CityStaff
from postgres.models.llc import Llc, PropertyLlc
from postgres.models.log_entry import LogEntry
from postgres.models.officer import Officer
from postgres.models.pdf_url import PdfUrl
from postgres.models.property import Property
from postgres.models.property_sale import PropertySale
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

_LLC_PATTERN = re.compile(
    r"\b(LLC|L\.L\.C|INC|CORP|CORPORATION|TRUST|LP|LLP|PLLC)\b",
    re.IGNORECASE,
)


class UrlRecordPipeline:
    def open_spider(self, spider) -> None:
        self._records: list[UrlRecord] = []

    def process_item(self, item, spider):
        if not isinstance(item, UrlRecordItem):
            return item

        self._records.append(UrlRecord.model_validate(dict(item)))
        return item

    def close_spider(self, spider) -> None:
        # Every spider runs this pipeline, so only open a session when there are URLs.
        if not self._records:
            return

        statement = (
            pg_insert(PdfUrl)
            .values([record.model_dump() for record in self._records])
            .on_conflict_do_nothing(index_elements=["canonical_url"])
        )
        with (
            logfire.span("insert pdf urls", found=len(self._records)),
            SessionLocal() as session,
        ):
            result = session.execute(statement)
            session.commit()
            logfire.info(
                "pdf urls flushed", found=len(self._records), inserted=result.rowcount
            )


class PoliceLogPipeline:
    def open_spider(self, spider) -> None:
        self._session = SessionLocal()

    def process_item(self, item, spider):
        if not isinstance(item, PoliceLogPdfItem):
            return item

        try:
            records = [
                PoliceLogRecord.model_validate(dict(entry)) for entry in item["entries"]
            ]
            with logfire.span(
                "save police log entries", url_id=item["url_id"], count=len(records)
            ):
                for record in records:
                    self._session.execute(_log_entry_insert(record))
                self._session.execute(
                    _pdf_url_update(
                        item["url_id"],
                        state="complete",
                        raw_text=item["raw_text"],
                        entry_count=len(records),
                    )
                )
                self._session.commit()
        except Exception as exc:
            self._session.rollback()
            self._session.execute(
                _pdf_url_update(
                    item["url_id"],
                    state="error",
                    error_message=f"Saving entries failed: {exc}",
                )
            )
            self._session.commit()
            raise

        return item

    def close_spider(self, spider) -> None:
        self._session.close()


def _pdf_url_update(url_id: int, **values):
    # pdf_urls timestamps are naive columns that hold UTC, like the other tables.
    completed_at = datetime.now(UTC).replace(tzinfo=None)
    return (
        update(PdfUrl)
        .where(PdfUrl.id == url_id)
        .values(completed_at=completed_at, **values)
    )


def _log_entry_insert(record: PoliceLogRecord):
    return (
        pg_insert(LogEntry)
        .values(
            source_url=record.source_url,
            case_number=record.case_number,
            reported_at=record.reported_at,
            call_source=record.call_source,
            incident_type=record.incident_type,
            disposition=record.disposition,
            raw_reason_action=record.raw_reason_action,
            location=record.location,
            officer=record.officer,
            reference_number=record.reference_number,
            dispatched_at=record.dispatched_at,
            enroute_at=record.enroute_at,
            arrived_at=record.arrived_at,
            cleared_at=record.cleared_at,
            response_seconds=record.response_seconds,
            scene_seconds=record.scene_seconds,
            raw_text=record.raw_text,
            parse_error=record.parse_error,
            scraped_at=record.scraped_at,
        )
        .on_conflict_do_nothing(index_elements=["case_number"])
    )


class PropertyPipeline:
    def open_spider(self, spider) -> None:
        self._session = SessionLocal()

    def process_item(self, item, spider):
        if not isinstance(item, PropertyItem):
            return item

        record = PropertyRecord.model_validate(dict(item))

        try:
            now = datetime.now(UTC).replace(tzinfo=None)

            with logfire.span("save property", parcel_id=record.parcel_id):
                # Upsert property
                stmt = (
                    pg_insert(Property)
                    .values(
                        parcel_id=record.parcel_id,
                        location=record.location,
                        owner=record.owner,
                        owner_address=record.owner_address,
                        land_use=record.land_use,
                        lot_size_acres=record.lot_size_acres,
                        year_built=record.year_built,
                        building_sqft=record.building_sqft,
                        assessed_land=record.assessed_land,
                        assessed_building=record.assessed_building,
                        assessed_total=record.assessed_total,
                        assessment_year=record.assessment_year,
                        detail_url=record.detail_url,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=["parcel_id"],
                        set_={
                            "location": record.location,
                            "owner": record.owner,
                            "owner_address": record.owner_address,
                            "land_use": record.land_use,
                            "lot_size_acres": record.lot_size_acres,
                            "year_built": record.year_built,
                            "building_sqft": record.building_sqft,
                            "assessed_land": record.assessed_land,
                            "assessed_building": record.assessed_building,
                            "assessed_total": record.assessed_total,
                            "assessment_year": record.assessment_year,
                            "detail_url": record.detail_url,
                            "updated_at": now,
                        },
                    )
                )
                self._session.execute(stmt)

                # Get the property PK to link sales
                property_id = self._session.execute(
                    select(Property.id).where(Property.parcel_id == record.parcel_id)
                ).scalar_one()

                # Queue LLC lookup if owner looks like a business entity
                if record.owner and _LLC_PATTERN.search(record.owner):
                    normalized = record.owner.strip().upper()
                    self._session.execute(
                        pg_insert(Llc)
                        .values(
                            name=normalized,
                            raw_owner_name=record.owner,
                            lookup_status="pending",
                            created_at=now,
                        )
                        .on_conflict_do_nothing(index_elements=["name"])
                    )
                    llc_id = self._session.execute(
                        select(Llc.id).where(Llc.name == normalized)
                    ).scalar_one()
                    self._session.execute(
                        pg_insert(PropertyLlc)
                        .values(property_id=property_id, llc_id=llc_id)
                        .on_conflict_do_nothing()
                    )

                # Replace sales
                self._session.execute(
                    delete(PropertySale).where(PropertySale.property_id == property_id)
                )
                for sale in record.sales:
                    self._session.execute(
                        pg_insert(PropertySale).values(
                            property_id=property_id,
                            sale_date=sale.sale_date,
                            sale_price=sale.sale_price,
                            grantee=sale.grantee,
                            grantor=sale.grantor,
                            created_at=now,
                        )
                    )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return item

    def close_spider(self, spider) -> None:
        self._session.close()


class CityStaffPipeline:
    def open_spider(self, spider) -> None:
        self._session = SessionLocal()

    def process_item(self, item, spider):
        if not isinstance(item, CityStaffItem):
            return item

        record = CityStaffRecord.model_validate(dict(item))

        try:
            with logfire.span(
                "save city staff", name=record.name, department=record.department
            ):
                stmt = (
                    pg_insert(CityStaff)
                    .values(
                        name=record.name,
                        title=record.title,
                        department=record.department,
                        division=record.division,
                        email=record.email,
                        phone=record.phone,
                        source_url=record.source_url,
                        scraped_at=record.scraped_at,
                    )
                    .on_conflict_do_update(
                        constraint="uq_city_staff_name_dept",
                        set_={
                            "title": record.title,
                            "division": record.division,
                            "email": record.email,
                            "phone": record.phone,
                            "source_url": record.source_url,
                            "scraped_at": record.scraped_at,
                        },
                    )
                )
                self._session.execute(stmt)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return item

    def close_spider(self, spider) -> None:
        self._session.close()


class OfficerPipeline:
    def open_spider(self, spider) -> None:
        self._session = SessionLocal()

    def process_item(self, item, spider):
        if not isinstance(item, OfficerItem):
            return item

        record = OfficerRecord.model_validate(dict(item))

        try:
            with logfire.span("save officer", name=record.name):
                stmt = (
                    pg_insert(Officer)
                    .values(
                        name=record.name,
                        rank=record.rank,
                        division=record.division,
                        email=record.email,
                        phone=record.phone,
                        source_url=record.source_url,
                        scraped_at=record.scraped_at,
                    )
                    .on_conflict_do_update(
                        index_elements=["name"],
                        set_={
                            "rank": record.rank,
                            "division": record.division,
                            "email": record.email,
                            "phone": record.phone,
                            "source_url": record.source_url,
                            "scraped_at": record.scraped_at,
                        },
                    )
                )
                self._session.execute(stmt)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return item

    def close_spider(self, spider) -> None:
        self._session.close()


class BudgetDocumentPipeline:
    def open_spider(self, spider) -> None:
        self._session = SessionLocal()

    def process_item(self, item, spider):
        if not isinstance(item, BudgetDocumentItem):
            return item

        record = BudgetDocumentRecord.model_validate(dict(item))

        try:
            with logfire.span("save budget document", fiscal_year=record.fiscal_year):
                stmt = (
                    pg_insert(BudgetDocument)
                    .values(
                        fiscal_year=record.fiscal_year,
                        document_type=record.document_type,
                        source_url=record.source_url,
                        text_extracted=False,
                        scraped_at=record.scraped_at,
                    )
                    .on_conflict_do_update(
                        constraint="uq_budget_document_year_type",
                        set_={
                            "source_url": record.source_url,
                            "scraped_at": record.scraped_at,
                        },
                    )
                )
                self._session.execute(stmt)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return item

    def close_spider(self, spider) -> None:
        self._session.close()
