"""
Categorizes distinct incident_type values from log_entries that don't yet have
a row in incident_type_categories.

Modes (--mode flag):

  dump    Print uncategorized types as JSON to stdout.
          Use for manual subagent runs in Claude Code:
            uv run python scripts/categorize_incident_types.py --mode dump
          Then ask Claude Code to categorize and pipe results to import mode.

  import  Read categorized JSON from stdin, upsert to DB.
            cat categories.json | uv run python scripts/categorize_incident_types.py --mode import
          JSON format: [{"incident_type": "...", "category": "...", "subcategory": "..."}, ...]

  cli     Categorize using the claude CLI (claude --print).
          Routes through Claude Code subscription auth — no separate API key needed.
          Use for Airflow DAGs or scheduled jobs:
            uv run python scripts/categorize_incident_types.py --mode cli
          Requires: claude CLI installed and authenticated on the machine.

Idempotent — already-categorized types are skipped in all modes.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime

from dotenv import load_dotenv

load_dotenv()

from postgres import SessionLocal
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

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


def fetch_uncategorized(session: Session) -> list[str]:
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
        raise ValueError(f"No JSON array found in response: {cleaned[:200]}")

    rows = json.loads(match.group())
    result = []
    for row in rows:
        category = row.get("category", "")
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category {category!r} — must be one of {sorted(VALID_CATEGORIES)}"
            )
        result.append(
            {
                "incident_type": row["incident_type"],
                "category": category,
                "subcategory": row.get("subcategory") or None,
            }
        )
    return result


def upsert_categories(session: Session, rows: list[dict]) -> None:
    """Upsert categorized rows into incident_type_categories."""
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


def dump_uncategorized(session: Session) -> None:
    """Print uncategorized incident types as JSON to stdout."""
    types = fetch_uncategorized(session)
    print(json.dumps(types, indent=2))


def import_from_stdin(session: Session) -> None:
    """Read categorized JSON from stdin and upsert to DB."""
    rows = json.loads(sys.stdin.read())
    upsert_categories(session, rows)
    print(f"Upserted {len(rows)} categories.")


def run_via_cli(session: Session) -> None:
    """Categorize using the claude CLI (routes through Claude Code auth)."""
    types = fetch_uncategorized(session)
    if not types:
        print("Nothing to categorize — all incident types already have categories.")
        return

    print(f"Found {len(types)} uncategorized types.")

    all_rows: list[dict] = []
    for i in range(0, len(types), BATCH_SIZE):
        batch = types[i : i + BATCH_SIZE]
        prompt = _PROMPT_TEMPLATE.format(
            incident_types="\n".join(f"- {t}" for t in batch)
        )
        print(
            f"  Batch {i // BATCH_SIZE + 1}: calling claude CLI for {len(batch)} types..."
        )
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True,
            text=True,
            check=True,
        )
        rows = parse_claude_response(result.stdout)
        all_rows.extend(rows)

    upsert_categories(session, all_rows)
    print(f"Done. Upserted {len(all_rows)} categories.")


def categorize(mode: str) -> None:
    session = SessionLocal()
    try:
        if mode == "dump":
            dump_uncategorized(session)
        elif mode == "import":
            import_from_stdin(session)
        elif mode == "cli":
            run_via_cli(session)
        else:
            raise ValueError(f"Unknown mode: {mode!r}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["dump", "import", "cli"],
        default="cli",
        help="dump: print uncategorized types | import: read JSON from stdin | cli: use claude --print",
    )
    args = parser.parse_args()
    categorize(args.mode)
