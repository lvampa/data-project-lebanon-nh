"""
Scrape Lebanon NH CivicClerk Planning Board meetings and documents.

Uses Playwright browser request context to bypass WAF that blocks plain HTTP clients.
The CivicClerk API (https://lebanonh.api.civicclerk.com/v1/) is public OData v4 but
returns 404 to non-browser user-agents.
"""
import io
import argparse
import asyncio
from datetime import UTC, datetime


PORTAL_BASE = "https://lebanonh.portal.civicclerk.com"
API_BASE = "https://lebanonh.api.civicclerk.com/v1"
FILE_TYPE_MAP = {1: "Agenda", 2: "Minutes", 3: "Attachment"}


def parse_event(data: dict, category_name: str) -> dict:
    raw_date = data.get("eventStartDate")
    meeting_date: datetime | None = None
    if raw_date:
        try:
            meeting_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass

    status_obj = data.get("status") or {}
    event_id = data["id"]
    return {
        "civicclerk_event_id": event_id,
        "title": data.get("title"),
        "category": category_name,
        "meeting_date": meeting_date,
        "location": data.get("location"),
        "status": status_obj.get("description") if isinstance(status_obj, dict) else None,
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
    except Exception:
        return None


async def fetch_planning_category_id(request_ctx) -> tuple[int, str]:
    resp = await request_ctx.get(f"{API_BASE}/EventCategories")
    data = await resp.json()
    categories = data.get("value", data) if isinstance(data, dict) else data
    for cat in categories:
        name = cat.get("name", "") or cat.get("title", "")
        if "planning" in name.lower():
            return cat["id"], name
    raise RuntimeError(f"Planning Board category not found. Got: {[c.get('name') for c in categories]}")


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


async def run(limit: int) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    from playwright.async_api import async_playwright
    import logfire
    from postgres import SessionLocal
    from postgres.models.planning_meeting import PlanningMeeting
    from postgres.models.planning_document import PlanningDocument
    from sqlalchemy.dialects.postgresql import insert as pg_insert

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
            for raw in raw_events:
                event_id = raw["id"]
                meeting = parse_event(raw, category_name)
                meeting["scraped_at"] = now

                with logfire.span("upsert meeting", event_id=event_id):
                    session.execute(
                        pg_insert(PlanningMeeting)
                        .values(**meeting)
                        .on_conflict_do_update(
                            index_elements=["civicclerk_event_id"],
                            set_={k: v for k, v in meeting.items() if k != "civicclerk_event_id"},
                        )
                    )

                for raw_file in raw.get("publishedFiles") or []:
                    doc = parse_file(raw_file, event_id)
                    try:
                        file_resp = await request_ctx.get(doc["download_url"])
                        raw_bytes = await file_resp.body()
                    except Exception as exc:
                        logfire.warning("file download failed", file_id=doc["civicclerk_file_id"], error=str(exc))
                        raw_bytes = b""
                    doc["raw_text"] = extract_text_from_pdf(raw_bytes)
                    doc["scraped_at"] = now
                    with logfire.span("upsert document", file_id=doc["civicclerk_file_id"]):
                        session.execute(
                            pg_insert(PlanningDocument)
                            .values(**doc)
                            .on_conflict_do_update(
                                index_elements=["civicclerk_file_id"],
                                set_={k: v for k, v in doc.items() if k != "civicclerk_file_id"},
                            )
                        )

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
