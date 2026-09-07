"""
Import structured budget data from scripts/data/budget_data.json
(produced by a Claude Code agent) into Postgres.

Run from repo root:
    uv run python scripts/import_budget_data.py

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

DATA_DIR = Path(__file__).parent / "data"
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


def validate_year_entry(entry: dict) -> None:
    if "fiscal_year" not in entry:
        raise ValueError(f"Entry missing 'fiscal_year': {entry}")
    if not isinstance(entry["fiscal_year"], int):
        raise ValueError(
            f"fiscal_year must be an integer, got {entry['fiscal_year']!r}"
        )


def upsert_line_items(session, fiscal_year: int, items: list[dict]) -> int:
    if not items:
        return 0
    for item in items:
        stmt = (
            pg_insert(BudgetLineItem)
            .values(
                fiscal_year=fiscal_year,
                gl_number=item["gl_number"],
                fund_code=item["fund_code"],
                fund_name=item["fund_name"],
                department=item["department"],
                description=item["description"],
                prior_year_amended=item.get("prior_year_amended"),
                year_requested=item.get("year_requested"),
                year_approved=item.get("year_approved"),
            )
            .on_conflict_do_update(
                constraint="uq_budget_line_item_year_gl",
                set_={
                    "fund_code": item["fund_code"],
                    "fund_name": item["fund_name"],
                    "department": item["department"],
                    "description": item["description"],
                    "prior_year_amended": item.get("prior_year_amended"),
                    "year_requested": item.get("year_requested"),
                    "year_approved": item.get("year_approved"),
                },
            )
        )
        session.execute(stmt)
    return len(items)


def upsert_capital_projects(session, fiscal_year: int, projects: list[dict]) -> int:
    if not projects:
        return 0
    for project in projects:
        stmt = (
            pg_insert(BudgetCapitalProject)
            .values(
                fiscal_year=fiscal_year,
                gl_number=project["gl_number"],
                project_name=project["project_name"],
                fund_code=project["fund_code"],
                fund_name=project["fund_name"],
                year_requested=project.get("year_requested"),
                year_approved=project.get("year_approved"),
            )
            .on_conflict_do_update(
                constraint="uq_budget_capital_project_year_gl",
                set_={
                    "project_name": project["project_name"],
                    "fund_code": project["fund_code"],
                    "fund_name": project["fund_name"],
                    "year_requested": project.get("year_requested"),
                    "year_approved": project.get("year_approved"),
                },
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
    entries = parse_budget_data(text)

    with SessionLocal() as session:
        for entry in entries:
            validate_year_entry(entry)
            fiscal_year = entry["fiscal_year"]
            with logfire.span("import budget year", fiscal_year=fiscal_year):
                n_items = upsert_line_items(
                    session, fiscal_year, entry.get("line_items", [])
                )
                n_projects = upsert_capital_projects(
                    session, fiscal_year, entry.get("capital_projects", [])
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
