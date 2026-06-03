"""
Categorizes all distinct incident_type values in log_entries that don't yet
have a row in incident_type_categories, using claude-haiku-4-5-20251001.

Run from scrapers/:
    uv run python scripts/categorize_incident_types.py

Idempotent — already-categorized types are skipped.
"""
import json
import re
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

import anthropic
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from postgres import SessionLocal
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry

VALID_CATEGORIES = {"Fire", "EMS", "Police", "Traffic", "Administrative"}
BATCH_SIZE = 50

_PROMPT_TEMPLATE = """\
You are categorizing Lebanon NH emergency dispatch incident types for a civic data product.

Given the list of incident types below, return a JSON array where each element has:
- "incident_type": the exact string from the input (no changes)
- "category": exactly one of ["Fire", "EMS", "Police", "Traffic", "Administrative"]
- "subcategory": a concise specific label (e.g. "Structure Fire", "Overdose", "Domestic Disturbance", "MV Accident", "Broadcast Log")

Category guidance:
- Fire: anything starting with "FD" (Fire Department calls)
- EMS: medical emergencies, overdoses, mental health crises
- Police: criminal incidents, welfare checks, noise complaints, warrants
- Traffic: vehicle accidents, traffic stops, road hazards, parking
- Administrative: BOL/ATL broadcasts, log information, records requests, system entries

Return ONLY the JSON array with no additional text.

Incident types to categorize:
{incident_types}
"""


def fetch_uncategorized(session) -> list[str]:
    """Return distinct incident_type values not yet in incident_type_categories."""
    already = select(IncidentTypeCategory.raw_incident_type)
    stmt = (
        select(LogEntry.incident_type)
        .where(
            LogEntry.incident_type.isnot(None),
            LogEntry.incident_type != "",
            LogEntry.incident_type.not_in(already),
        )
        .distinct()
        .order_by(LogEntry.incident_type)
    )
    return session.execute(stmt).scalars().all()


def parse_claude_response(text: str) -> list[dict]:
    """
    Parse Claude's JSON response into a list of category dicts.
    Strips markdown fences if present. Validates category values.
    Missing subcategory defaults to None.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in response: {text[:200]}")

    rows = json.loads(match.group())
    result = []
    for row in rows:
        category = row.get("category", "")
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category {category!r} — must be one of {VALID_CATEGORIES}")
        result.append({
            "incident_type": row["incident_type"],
            "category": category,
            "subcategory": row.get("subcategory") or None,
        })
    return result


def upsert_categories(session, rows: list[dict]) -> None:
    """Upsert categorized rows into incident_type_categories."""
    if not rows:
        return

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for row in rows:
        stmt = pg_insert(IncidentTypeCategory).values(
            raw_incident_type=row["incident_type"],
            category=row["category"],
            subcategory=row["subcategory"],
            created_at=now,
            updated_at=now,
        ).on_conflict_do_update(
            index_elements=["raw_incident_type"],
            set_={
                "category": row["category"],
                "subcategory": row["subcategory"],
                "updated_at": now,
            },
        )
        session.execute(stmt)
    session.commit()


def _call_claude(incident_types: list[str]) -> list[dict]:
    client = anthropic.Anthropic()
    prompt = _PROMPT_TEMPLATE.format(
        incident_types="\n".join(f"- {t}" for t in incident_types)
    )
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_claude_response(message.content[0].text)


def categorize() -> None:
    session = SessionLocal()
    try:
        uncategorized = fetch_uncategorized(session)
        if not uncategorized:
            print("Nothing to categorize — all incident types already have categories.")
            return

        print(f"Found {len(uncategorized)} uncategorized incident types.")

        total_upserted = 0
        for i in range(0, len(uncategorized), BATCH_SIZE):
            batch = uncategorized[i : i + BATCH_SIZE]
            print(f"  Batch {i // BATCH_SIZE + 1}: categorizing {len(batch)} types...")
            rows = _call_claude(batch)
            upsert_categories(session, rows)
            total_upserted += len(rows)
            print(f"    → upserted {len(rows)} rows")

        print(f"Done. Total upserted: {total_upserted}")
    finally:
        session.close()


if __name__ == "__main__":
    categorize()
