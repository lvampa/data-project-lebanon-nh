import json
import re
from datetime import datetime, timezone
from pathlib import Path

import logfire
from sqlalchemy.dialects.postgresql import insert as pg_insert

from postgres import SessionLocal
from postgres.models.incident_type_category import IncidentTypeCategory

DATA_DIR = Path(__file__).parent / "data"
INPUT_FILE = DATA_DIR / "incident_categories.json"

VALID_CATEGORIES = {"Fire", "EMS", "Police", "Traffic", "Administrative"}


def parse_categories(text: str) -> list[dict]:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in: {text[:200]}")
    rows = json.loads(match.group())
    result = []
    for row in rows:
        category = row.get("category", "")
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category {category!r} — must be one of {VALID_CATEGORIES}"
            )
        result.append({
            "incident_type": row["incident_type"],
            "category": category,
            "subcategory": row.get("subcategory") or None,
        })
    return result


def upsert_categories(session, rows: list[dict]) -> None:
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


def main() -> None:
    logfire.configure()
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"{INPUT_FILE} not found — run the Claude Code job first to generate it"
        )
    text = INPUT_FILE.read_text(encoding="utf-8")
    rows = parse_categories(text)
    with SessionLocal() as session:
        with logfire.span("import incident categories", count=len(rows)):
            upsert_categories(session, rows)
            logfire.info("upserted {count} categories", count=len(rows))


if __name__ == "__main__":
    main()
