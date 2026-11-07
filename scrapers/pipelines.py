import re
from datetime import UTC, datetime

import logfire
from ingest import ingest_pdf_url
from ingest.pdf_urls import kept_for_reprocess, mark_error
from items import PoliceLogPdfItem, UrlRecordItem
from items.budget import BudgetDocumentItem
from items.city_staff import CityStaffItem
from items.officer import OfficerItem
from items.property import PropertyItem
from models.budget_document import BudgetDocumentRecord
from models.city_staff import CityStaffRecord
from models.officer import OfficerRecord
from models.property import PropertyRecord
from models.url_record import UrlRecord
from postgres import SessionLocal
from postgres.models.budget_document import BudgetDocument
from postgres.models.city_staff import CityStaff
from postgres.models.llc import Llc, PropertyLlc
from postgres.models.officer import Officer
from postgres.models.pdf_url import PdfUrl
from postgres.models.property import Property
from postgres.models.property_sale import PropertySale
from sqlalchemy import delete, select
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

        url_id = item["url_id"]
        try:
            with logfire.span("ingest police log pdf", url_id=url_id):
                pdf_url = self._session.get(PdfUrl, url_id)
                counts = ingest_pdf_url(
                    self._session,
                    pdf_url,
                    item["raw_text"],
                    content_hash=item["content_hash"],
                    original_archived=item["original_archived"],
                )
                # One commit, so the URL is never complete without its entries.
                self._session.commit()
                logfire.info(
                    "police log pdf ingested",
                    url_id=url_id,
                    parsed=counts.parsed,
                    stored=counts.stored,
                    skipped=counts.skipped,
                )
        except Exception as exc:
            self._session.rollback()
            kind = kept_for_reprocess("save", item["original_archived"])
            self._session.execute(
                mark_error(url_id, kind, f"Saving entries failed: {exc}")
            )
            self._session.commit()
            raise

        return item

    def close_spider(self, spider) -> None:
        self._session.close()


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
