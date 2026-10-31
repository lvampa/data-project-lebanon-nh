"""
Import structured budget data from scripts/data/budget_data.json
(produced by a Claude Code agent) into Postgres.

Run from repo root:
    uv run python scripts/ingest/import_budget_data.py

Input: scripts/data/budget_data.json
Format: array of year objects, each with 'line_items' and 'capital_projects' arrays
Idempotent — uses ON CONFLICT DO UPDATE.
"""

import json
import re
from pathlib import Path

import logfire
from postgres import SessionLocal
from postgres.models.budget_capital_project import BudgetCapitalProject
from postgres.models.budget_line_item import BudgetLineItem
from sqlalchemy.dialects.postgresql import insert as pg_insert

from scripts.models import (
    BudgetCapitalProjectRecord,
    BudgetLineItemRecord,
    BudgetYearRecord,
)

DATA_DIR = Path(__file__).parents[1] / "data"
INPUT_FILE = DATA_DIR / "budget_data.json"


def parse_budget_data(text: str) -> list[dict]:
    cleaned = re.sub(r"^```(?:json)?\s*$", "", text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse JSON: {e}\nInput (first 200 chars): {text[:200]}"
        ) from e
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array, got {type(data).__name__}")
    return data


def validate_year_entry(entry: dict) -> BudgetYearRecord:
    return BudgetYearRecord.model_validate(entry)


def upsert_line_items(
    session, fiscal_year: int, items: list[BudgetLineItemRecord]
) -> int:
    if not items:
        return 0
    for item in items:
        values = item.model_dump()
        stmt = (
            pg_insert(BudgetLineItem)
            .values(fiscal_year=fiscal_year, **values)
            .on_conflict_do_update(
                constraint="uq_budget_line_item_year_gl",
                set_={k: v for k, v in values.items() if k != "gl_number"},
            )
        )
        session.execute(stmt)
    return len(items)


def upsert_capital_projects(
    session, fiscal_year: int, projects: list[BudgetCapitalProjectRecord]
) -> int:
    if not projects:
        return 0
    for project in projects:
        values = project.model_dump()
        stmt = (
            pg_insert(BudgetCapitalProject)
            .values(fiscal_year=fiscal_year, **values)
            .on_conflict_do_update(
                constraint="uq_budget_capital_project_year_gl",
                set_={k: v for k, v in values.items() if k != "gl_number"},
            )
        )
        session.execute(stmt)
    return len(projects)


def main() -> None:
    logfire.configure()
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"{INPUT_FILE} not found — run the Claude Code agent first to generate it"
        )
    text = INPUT_FILE.read_text(encoding="utf-8")
    # Validate every year before writing any, so a bad year late in the file
    # does not leave a partial import behind.
    years = [validate_year_entry(entry) for entry in parse_budget_data(text)]

    with SessionLocal() as session:
        for year in years:
            fiscal_year = year.fiscal_year
            with logfire.span("import budget year", fiscal_year=fiscal_year):
                n_items = upsert_line_items(session, fiscal_year, year.line_items)
                n_projects = upsert_capital_projects(
                    session, fiscal_year, year.capital_projects
                )
                session.commit()
                logfire.info(
                    "imported {year}: {items} line items, {projects} capital projects",
                    year=fiscal_year,
                    items=n_items,
                    projects=n_projects,
                )


if __name__ == "__main__":
    main()
