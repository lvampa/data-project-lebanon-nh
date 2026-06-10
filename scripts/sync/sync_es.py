"""
Sync all Postgres entities to Elasticsearch.

Run from repo root:
    uv run python scripts/sync/sync_es.py

Idempotent — uses document _id = Postgres id, so re-runs upsert in place.
"""
import os

import logfire
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from sqlalchemy import select

from postgres import SessionLocal
from postgres.models.address_normalization import AddressNormalization
from postgres.models.budget_capital_project import BudgetCapitalProject
from postgres.models.budget_line_item import BudgetLineItem
from postgres.models.city_staff import CityStaff
from postgres.models.llc import Llc
from postgres.models.log_entry import LogEntry
from postgres.models.officer import Officer
from postgres.models.planning_document import PlanningDocument
from postgres.models.planning_meeting import PlanningMeeting
from postgres.models.property import Property

ES_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")


def get_address_lookup(session) -> dict[str, dict]:
    rows = session.execute(select(AddressNormalization)).scalars().all()
    return {
        r.raw_address: {
            "normalized_address": r.normalized_address,
            "lat": r.lat,
            "lng": r.lng,
        }
        for r in rows
    }


def _resolve_address(raw: str | None, lookup: dict) -> tuple[str | None, float | None, float | None]:
    if not raw:
        return None, None, None
    entry = lookup.get(raw)
    if entry:
        return entry["normalized_address"], entry["lat"], entry["lng"]
    return raw, None, None


def build_property_doc(row, address_lookup: dict) -> dict:
    norm, lat, lng = _resolve_address(row.location, address_lookup)
    return {
        "id": row.id,
        "entity_type": "properties",
        "parcel_id": row.parcel_id,
        "location": row.location,
        "owner": row.owner,
        "owner_address": row.owner_address,
        "land_use": row.land_use,
        "assessed_total": float(row.assessed_total) if row.assessed_total else None,
        "year_built": row.year_built,
        "normalized_address": norm,
        "lat": lat,
        "lng": lng,
    }


def build_incident_doc(row, address_lookup: dict) -> dict:
    norm, lat, lng = _resolve_address(row.location, address_lookup)
    return {
        "id": row.id,
        "entity_type": "incidents",
        "case_number": row.case_number,
        "incident_type": row.incident_type,
        "location": row.location,
        "officer": row.officer,
        "disposition": row.disposition,
        "reported_at": row.reported_at.isoformat() if row.reported_at else None,
        "raw_text": row.raw_text,
        "normalized_address": norm,
        "lat": lat,
        "lng": lng,
    }


def build_planning_meeting_doc(row, address_lookup: dict) -> dict:
    norm, lat, lng = _resolve_address(row.location, address_lookup)
    return {
        "id": row.id,
        "entity_type": "planning_meetings",
        "civicclerk_event_id": row.civicclerk_event_id,
        "title": row.title,
        "category": row.category,
        "meeting_date": row.meeting_date.isoformat() if row.meeting_date else None,
        "status": row.status,
        "location": row.location,
        "normalized_address": norm,
        "lat": lat,
        "lng": lng,
    }


def build_planning_document_doc(row, meeting_lookup: dict) -> dict:
    entry = meeting_lookup.get(row.civicclerk_event_id, {})
    return {
        "id": row.id,
        "entity_type": "planning_documents",
        "civicclerk_file_id": row.civicclerk_file_id,
        "civicclerk_event_id": row.civicclerk_event_id,
        "file_name": row.file_name,
        "file_type": row.file_type,
        "raw_text": row.raw_text,
        "normalized_address": entry.get("normalized_address"),
        "lat": entry.get("lat"),
        "lng": entry.get("lng"),
    }


def build_city_staff_doc(row) -> dict:
    return {
        "id": row.id,
        "entity_type": "city_staff",
        "name": row.name,
        "title": row.title,
        "department": row.department,
        "division": row.division,
    }


def build_officer_doc(row) -> dict:
    return {
        "id": row.id,
        "entity_type": "officers",
        "name": row.name,
        "rank": row.rank,
        "division": row.division,
    }


def build_llc_doc(row) -> dict:
    return {
        "id": row.id,
        "entity_type": "llcs",
        "name": row.name,
        "raw_owner_name": row.raw_owner_name,
    }


def build_budget_line_item_doc(row) -> dict:
    return {
        "id": row.id,
        "entity_type": "budget_line_items",
        "fiscal_year": row.fiscal_year,
        "department": row.department,
        "description": row.description,
        "fund_name": row.fund_name,
    }


def build_budget_capital_project_doc(row) -> dict:
    return {
        "id": row.id,
        "entity_type": "budget_capital_projects",
        "fiscal_year": row.fiscal_year,
        "project_name": row.project_name,
        "fund_name": row.fund_name,
    }


def sync_index(es: Elasticsearch, index: str, rows: list, build_fn) -> int:
    if not rows:
        return 0
    actions = (
        {
            "_op_type": "index",
            "_index": index,
            "_id": str(row.id),
            "_source": build_fn(row),
        }
        for row in rows
    )
    bulk(es, actions)
    return len(rows)


def main() -> None:
    logfire.configure()
    es = Elasticsearch(ES_HOST)

    with SessionLocal() as session:
        address_lookup = get_address_lookup(session)

        meetings = session.execute(select(PlanningMeeting)).scalars().all()
        meeting_lookup: dict[int, dict] = {}
        for m in meetings:
            norm, lat, lng = _resolve_address(m.location, address_lookup)
            meeting_lookup[m.civicclerk_event_id] = {"normalized_address": norm, "lat": lat, "lng": lng}

        syncs = [
            ("properties",              session.execute(select(Property)).scalars().all(),              lambda r: build_property_doc(r, address_lookup)),
            ("incidents",               session.execute(select(LogEntry)).scalars().all(),              lambda r: build_incident_doc(r, address_lookup)),
            ("planning_meetings",       meetings,                                                        lambda r: build_planning_meeting_doc(r, address_lookup)),
            ("planning_documents",      session.execute(select(PlanningDocument)).scalars().all(),      lambda r: build_planning_document_doc(r, meeting_lookup)),
            ("city_staff",              session.execute(select(CityStaff)).scalars().all(),             build_city_staff_doc),
            ("officers",                session.execute(select(Officer)).scalars().all(),               build_officer_doc),
            ("llcs",                    session.execute(select(Llc)).scalars().all(),                   build_llc_doc),
            ("budget_line_items",       session.execute(select(BudgetLineItem)).scalars().all(),        build_budget_line_item_doc),
            ("budget_capital_projects", session.execute(select(BudgetCapitalProject)).scalars().all(),  build_budget_capital_project_doc),
        ]

        for index, rows, build_fn in syncs:
            with logfire.span("sync index", index=index):
                count = sync_index(es, index, rows, build_fn)
                logfire.info("synced {index}: {count} docs", index=index, count=count)


if __name__ == "__main__":
    main()
