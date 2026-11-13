import argparse
import asyncio
import contextlib
import random
from datetime import UTC, datetime, timedelta

import logfire
from bs4 import BeautifulSoup
from postgres.models.llc import Llc
from sqlalchemy import Update, or_, update

from scripts.models import LlcLookupRecord

SEARCH_URL = "https://quickstart.sos.nh.gov/online/BusinessInquire/"
# Matches the police-log URL queue. A run that dies mid-batch leaves its rows
# in_progress; after this long they go back to pending.
CLAIM_LEASE = timedelta(hours=2)


def parse_llc_detail(html: str, business_id: str | None) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    def find_labeled_value(label: str) -> str | None:
        for td in soup.find_all("td"):
            if td.get_text(strip=True) == label:
                sibling = td.find_next_sibling("td")
                if sibling:
                    return sibling.get_text(strip=True) or None
        return None

    raw_date = find_labeled_value("Business Creation Date:")
    formation_date = None
    if raw_date:
        with contextlib.suppress(ValueError):
            formation_date = datetime.strptime(raw_date, "%m/%d/%Y").date()

    principals = []
    for row in soup.select("table tbody tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            name_title = cells[0].get_text(strip=True)
            address = cells[1].get_text(strip=True)
            if " / " in name_title:
                name, title = name_title.split(" / ", 1)
                principals.append(
                    {"name": name.strip(), "title": title.strip(), "address": address}
                )

    agent_div = soup.find(id="registered-agent")
    registered_agent = None
    registered_agent_address = None
    if agent_div:
        for p in agent_div.find_all("p"):
            text = p.get_text(strip=True)
            if text.startswith("Name:"):
                registered_agent = text.removeprefix("Name:").strip()
            elif text.startswith("Registered Office Address:"):
                registered_agent_address = text.removeprefix(
                    "Registered Office Address:"
                ).strip()

    return {
        "nh_business_id": business_id or None,
        "business_status": find_labeled_value("Business Status:"),
        "formation_date": formation_date,
        "business_email": find_labeled_value("Business Email:"),
        "phone": find_labeled_value("Phone #:"),
        "registered_agent": registered_agent,
        "registered_agent_address": registered_agent_address,
        "principals": principals or None,
    }


async def scrape_llc(page, name: str) -> tuple[str | None, dict | None]:
    """Search NH SOS for an LLC by name. Returns (business_id, parsed_data) or (None, None)."""
    await page.goto(SEARCH_URL)
    await page.fill("input[name*='BusinessName'], input[id*='BusinessName']", name)
    await page.click("input[type='submit'], button[type='submit']")
    await page.wait_for_load_state("networkidle")

    first_result = page.locator("table tbody tr td a").first
    if not await first_result.count():
        return None, None

    href = await first_result.get_attribute("href")
    business_id = None
    if href and "businessID=" in href:
        business_id = href.split("businessID=")[-1]

    await first_result.click()
    await page.wait_for_load_state("networkidle")

    html = await page.content()
    if not business_id:
        business_id = (
            page.url.split("businessID=")[-1] if "businessID=" in page.url else None
        )

    return business_id, parse_llc_detail(html, business_id)


def release_stale_claims(now: datetime) -> Update:
    # The claim stamps last_looked_up_at, so it doubles as the claim time.
    # Rows claimed before that stamp existed have NULL and are stale too.
    lease_cutoff = now - CLAIM_LEASE
    return (
        update(Llc)
        .where(
            Llc.lookup_status == "in_progress",
            or_(Llc.last_looked_up_at.is_(None), Llc.last_looked_up_at < lease_cutoff),
        )
        .values(lookup_status="pending")
    )


def save_lookup(session, llc_id: int, data: dict | None, now: datetime) -> None:
    if data is None:
        values = {"lookup_status": "error", "error_message": "Not found on NH SOS"}
    else:
        record = LlcLookupRecord.model_validate(data)
        values = {"lookup_status": "complete", "error_message": None}
        values |= record.model_dump()
    with logfire.span(
        "save llc lookup", llc_id=llc_id, lookup_status=values["lookup_status"]
    ):
        session.execute(
            update(Llc).where(Llc.id == llc_id).values(last_looked_up_at=now, **values)
        )
        session.commit()


async def run(limit: int) -> None:
    from dotenv import load_dotenv

    load_dotenv()
    logfire.configure()

    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
    from postgres import SessionLocal
    from sqlalchemy import select

    session = SessionLocal()
    try:
        released = session.execute(
            release_stale_claims(datetime.now(UTC).replace(tzinfo=None))
        ).rowcount
        session.commit()
        if released:
            logfire.warning("released stale llc claims", count=released)

        rows = session.scalars(
            select(Llc)
            .where(Llc.lookup_status == "pending")
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()

        if not rows:
            logfire.info("no pending llcs to process")
            return

        ids = [r.id for r in rows]
        session.execute(
            update(Llc)
            .where(Llc.id.in_(ids))
            .values(
                lookup_status="in_progress",
                last_looked_up_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        session.commit()
        logfire.info("claimed llcs", count=len(ids))

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await Stealth().apply_stealth_async(page)

            for llc in rows:
                logfire.info("looking up llc", llc_id=llc.id, name=llc.name)
                try:
                    _business_id, data = await scrape_llc(page, llc.name)
                    now = datetime.now(UTC).replace(tzinfo=None)
                    save_lookup(session, llc.id, data, now)
                except Exception as e:
                    session.rollback()
                    session.execute(
                        update(Llc)
                        .where(Llc.id == llc.id)
                        .values(
                            lookup_status="error",
                            error_message=str(e),
                            last_looked_up_at=datetime.now(UTC).replace(tzinfo=None),
                        )
                    )
                    session.commit()
                    logfire.warning("llc lookup failed", llc_id=llc.id, error=str(e))

                await asyncio.sleep(random.uniform(3, 5))

            await browser.close()
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(run(args.limit))
