import json
import re
from datetime import UTC, datetime
from pathlib import Path

import logfire
from postgres import SessionLocal
from postgres.models.incident_type_category import IncidentTypeCategory
from sqlalchemy.dialects.postgresql import insert as pg_insert

DATA_DIR = Path(__file__).parents[1] / "data"
INPUT_FILE = DATA_DIR / "incident_categories.json"

VALID_CATEGORIES = {"Fire", "EMS", "Police", "Traffic", "Administrative"}


def parse_categories(text: str) -> list[dict]:
    cleaned = re.sub(r"^```(?:json)?\s*$", "", text, flags=re.MULTILINE).strip()
    try:
        rows = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse JSON: {e}\nInput (first 200 chars): {text[:200]}"
        ) from e
    if not isinstance(rows, list):
        raise ValueError(f"Expected a JSON array, got {type(rows).__name__}")
    result = []
    for row in rows:
        category = row.get("category", "")
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category {category!r} — must be one of {VALID_CATEGORIES}"
            )
        if "incident_type" not in row:
            raise ValueError(f"Row missing 'incident_type': {row}")
        result.append(
            {
                "incident_type": row["incident_type"],
                "category": category,
                "subcategory": row.get("subcategory") or None,
            }
        )
    return result


def upsert_categories(session, rows: list[dict]) -> None:
    if not rows:
        return
    now = datetime.now(UTC).replace(tzinfo=None)
    for row in rows:
        stmt = (
            pg_insert(IncidentTypeCategory)
            .values(
                raw_incident_type=row["incident_type"],
                category=row["category"],
                subcategory=row["subcategory"],
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["raw_incident_type"],
                set_={
                    "category": row["category"],
                    "subcategory": row["subcategory"],
                    "updated_at": now,
                },
            )
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
    with (
        SessionLocal() as session,
        logfire.span("import incident categories", count=len(rows)),
    ):
        upsert_categories(session, rows)
        logfire.info("upserted {count} categories", count=len(rows))


if __name__ == "__main__":
    main()
