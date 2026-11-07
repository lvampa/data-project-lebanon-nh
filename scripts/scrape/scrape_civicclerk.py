"""
Scrape Lebanon NH CivicClerk Planning Board meetings and documents.

Uses Playwright browser request context to bypass WAF that blocks plain HTTP clients.
The CivicClerk API (https://lebanonh.api.civicclerk.com/v1/) is public OData v4 but
returns 404 to non-browser user-agents.
"""

import argparse
import asyncio
import contextlib
import io
from datetime import UTC, datetime

import logfire
from postgres.models.planning_document import PlanningDocument
from postgres.models.planning_meeting import PlanningMeeting
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from scripts.models import PlanningDocumentRecord, PlanningMeetingRecord

PORTAL_BASE = "https://lebanonh.portal.civicclerk.com"
API_BASE = "https://lebanonh.api.civicclerk.com/v1"
FILE_TYPE_MAP = {1: "Agenda", 2: "Minutes", 3: "Attachment"}


def parse_event(data: dict, category_name: str) -> dict:
    raw_date = data.get("eventStartDate")
    meeting_date: datetime | None = None
    if raw_date:
        with contextlib.suppress(ValueError):
            meeting_date = datetime.fromisoformat(
                raw_date.replace("Z", "+00:00")
            ).replace(tzinfo=None)

    status_obj = data.get("status") or {}
    event_id = data["id"]
    return {
        "civicclerk_event_id": event_id,
        "title": data.get("title"),
        "category": category_name,
        "meeting_date": meeting_date,
        "location": data.get("location"),
        "status": status_obj.get("description")
        if isinstance(status_obj, dict)
        else None,
        "source_url": f"{PORTAL_BASE}/event/{event_id}",
    }


def parse_file(data: dict, event_id: int) -> dict:
    file_id = data["id"]
    file_type_int = data.get("fileType", 0)
    stream_url = data.get("streamUrl")
    download_url = stream_url or (
        f"{API_BASE}/Events/GetEventFileStream(fileId={file_id},fileType={file_type_int},plainText=false)"
    )
    return {
        "civicclerk_file_id": file_id,
        "civicclerk_event_id": event_id,
        "file_name": data.get("name"),
        "file_type": FILE_TYPE_MAP.get(file_type_int, str(file_type_int)),
        "download_url": download_url,
    }


def extract_text_from_pdf(data: bytes) -> str | None:
    if not data or not data.startswith(b"%PDF"):
        return None
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages) or None
    except Exception as exc:
        logfire.warning("pdf text extraction failed", error=str(exc))
        return None


async def fetch_planning_category_id(request_ctx) -> tuple[int, str]:
    resp = await request_ctx.get(f"{API_BASE}/EventCategories")
    data = await resp.json()
    categories = data.get("value", data) if isinstance(data, dict) else data
    for cat in categories:
        name = cat.get("name", "") or cat.get("title", "")
        if "planning" in name.lower():
            return cat["id"], name
    raise RuntimeError(
        f"Planning Board category not found. Got: {[c.get('name') for c in categories]}"
    )


async def fetch_events(request_ctx, group_id: int, limit: int) -> list[dict]:
    events: list[dict] = []
    skip = 0
    page_size = 100
    while True:
        url = (
            f"{API_BASE}/Events"
            f"?$filter=eventGroupId eq {group_id}"
            f"&$top={page_size}&$skip={skip}"
            f"&$orderby=eventStartDate desc"
            f"&$expand=publishedFiles"
        )
        resp = await request_ctx.get(url)
        data = await resp.json()
        batch = data.get("value", data) if isinstance(data, dict) else data
        if not batch:
            break
        events.extend(batch)
        if limit and len(events) >= limit:
            return events[:limit]
        if len(batch) < page_size:
            break
        skip += page_size
    return events


def upsert_meeting(session, meeting: PlanningMeetingRecord) -> None:
    values = meeting.model_dump()
    with logfire.span("upsert meeting", event_id=meeting.civicclerk_event_id):
        session.execute(
            pg_insert(PlanningMeeting)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["civicclerk_event_id"],
                set_={k: v for k, v in values.items() if k != "civicclerk_event_id"},
            )
        )


def upsert_document(session, document: PlanningDocumentRecord) -> None:
    values = document.model_dump()
    updates = {k: v for k, v in values.items() if k != "civicclerk_file_id"}
    # A failed download or extraction yields no text; keep whatever was saved.
    if document.raw_text is None:
        del updates["raw_text"]
    with logfire.span("upsert document", file_id=document.civicclerk_file_id):
        session.execute(
            pg_insert(PlanningDocument)
            .values(**values)
            .on_conflict_do_update(index_elements=["civicclerk_file_id"], set_=updates)
        )


def file_ids_with_text(session, file_ids: list[int]) -> set[int]:
    if not file_ids:
        return set()
    return set(
        session.scalars(
            select(PlanningDocument.civicclerk_file_id).where(
                PlanningDocument.civicclerk_file_id.in_(file_ids),
                PlanningDocument.raw_text.isnot(None),
            )
        ).all()
    )


async def download_text(request_ctx, download_url: str, file_id: int) -> str | None:
    try:
        file_resp = await request_ctx.get(download_url)
        raw_bytes = await file_resp.body()
    except Exception as exc:
        logfire.warning("file download failed", file_id=file_id, error=str(exc))
        return None
    return extract_text_from_pdf(raw_bytes)


async def save_event(
    session, request_ctx, raw_event: dict, category_name: str, now: datetime
) -> None:
    meeting = PlanningMeetingRecord.model_validate(
        {**parse_event(raw_event, category_name), "scraped_at": now}
    )
    upsert_meeting(session, meeting)

    raw_files = raw_event.get("publishedFiles") or []
    already_extracted = file_ids_with_text(session, [f["id"] for f in raw_files])
    for raw_file in raw_files:
        doc = parse_file(raw_file, meeting.civicclerk_event_id)
        file_id = doc["civicclerk_file_id"]
        raw_text = None
        if file_id not in already_extracted:
            raw_text = await download_text(request_ctx, doc["download_url"], file_id)
        document = PlanningDocumentRecord.model_validate(
            {**doc, "raw_text": raw_text, "scraped_at": now}
        )
        upsert_document(session, document)


async def run(limit: int) -> None:
    from dotenv import load_dotenv

    load_dotenv()
    logfire.configure()

    from playwright.async_api import async_playwright
    from postgres import SessionLocal

    now = datetime.now(UTC).replace(tzinfo=None)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        # Warm up browser context with portal cookies/headers
        await page.goto(PORTAL_BASE, wait_until="domcontentloaded", timeout=30000)
        request_ctx = context.request

        with logfire.span("civicclerk fetch categories"):
            group_id, category_name = await fetch_planning_category_id(request_ctx)
            logfire.info("found planning category", id=group_id, name=category_name)

        with logfire.span("civicclerk fetch events", group_id=group_id):
            raw_events = await fetch_events(request_ctx, group_id, limit)
            logfire.info("fetched events", count=len(raw_events))

        session = SessionLocal()
        try:
            # Commit per meeting so one bad event or a crash late in a full
            # run does not throw away the downloads that already finished.
            for raw in raw_events:
                try:
                    await save_event(session, request_ctx, raw, category_name, now)
                except ValidationError as exc:
                    session.rollback()
                    logfire.warning(
                        "skipping invalid event", event_id=raw.get("id"), error=str(exc)
                    )
                    continue
                session.commit()
            logfire.info("civicclerk scrape complete", events=len(raw_events))
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max events (0=all)")
    args = parser.parse_args()
    asyncio.run(run(args.limit))
