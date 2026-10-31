import json
import re
from datetime import UTC, datetime
from pathlib import Path

import logfire
from postgres import SessionLocal
from postgres.models.incident_type_category import IncidentTypeCategory
from sqlalchemy.dialects.postgresql import insert as pg_insert

from scripts.models import IncidentCategoryRecord

DATA_DIR = Path(__file__).parents[1] / "data"
INPUT_FILE = DATA_DIR / "incident_categories.json"


def validate_categories(rows: object) -> list[IncidentCategoryRecord]:
    if not isinstance(rows, list):
        raise ValueError(f"Expected a JSON array, got {type(rows).__name__}")
    return [IncidentCategoryRecord.model_validate(row) for row in rows]


def parse_categories(text: str) -> list[IncidentCategoryRecord]:
    cleaned = re.sub(r"^```(?:json)?\s*$", "", text, flags=re.MULTILINE).strip()
    try:
        rows = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse JSON: {e}\nInput (first 200 chars): {text[:200]}"
        ) from e
    return validate_categories(rows)


def upsert_categories(session, rows: list[IncidentCategoryRecord]) -> None:
    if not rows:
        return
    now = datetime.now(UTC).replace(tzinfo=None)
    for row in rows:
        stmt = (
            pg_insert(IncidentTypeCategory)
            .values(
                raw_incident_type=row.incident_type,
                category=row.category,
                subcategory=row.subcategory,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["raw_incident_type"],
                set_={
                    "category": row.category,
                    "subcategory": row.subcategory,
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
