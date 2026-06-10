from pathlib import Path

import pytest

from scripts.scrape.download_budget_pdfs import extract_text, output_path


# --- output_path ---

def test_output_path_budget_book():
    p = output_path(2026, "budget_book")
    assert p.name == "2026-budget_book.txt"
    assert p.parent.name == "budgets"


def test_output_path_line_items():
    p = output_path(2025, "line_items")
    assert p.name == "2025-line_items.txt"


# --- extract_text ---

def test_extract_text_returns_string(tmp_path):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    pdf_path = tmp_path / "test.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)
    result = extract_text(pdf_path)
    assert isinstance(result, str)


def test_extract_text_joins_pages(tmp_path):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    pdf_path = tmp_path / "two_page.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)
    result = extract_text(pdf_path)
    assert isinstance(result, str)


from unittest.mock import MagicMock

from scripts.ingest.import_budget_data import (
    parse_budget_data,
    upsert_capital_projects,
    upsert_line_items,
    validate_year_entry,
)

VALID_JSON = """[
  {
    "fiscal_year": 2026,
    "line_items": [
      {
        "gl_number": "1100-4140-0000-1100-0000",
        "fund_code": "1100",
        "fund_name": "General Fund",
        "department": "City Clerk",
        "description": "FULL TIME WAGES",
        "prior_year_amended": 463070.00,
        "year_requested": 518350.00,
        "year_approved": 518350.00
      }
    ],
    "capital_projects": [
      {
        "gl_number": "1455-3359-4312-2009-7208-1455",
        "project_name": "TRUES BROOK BRIDGE",
        "fund_code": "1455",
        "fund_name": "CIP",
        "year_requested": 228070.00,
        "year_approved": 228070.00
      }
    ]
  }
]"""

MARKDOWN_FENCED = f"```json\n{VALID_JSON}\n```"


# --- parse_budget_data ---

def test_parse_valid_json():
    entries = parse_budget_data(VALID_JSON)
    assert len(entries) == 1
    assert entries[0]["fiscal_year"] == 2026
    assert len(entries[0]["line_items"]) == 1
    assert len(entries[0]["capital_projects"]) == 1


def test_parse_strips_markdown_fences():
    entries = parse_budget_data(MARKDOWN_FENCED)
    assert len(entries) == 1


def test_parse_empty_array():
    assert parse_budget_data("[]") == []


def test_parse_invalid_json_raises():
    with pytest.raises(ValueError, match="Could not parse JSON"):
        parse_budget_data("not json")


def test_parse_non_list_raises():
    with pytest.raises(ValueError, match="Expected a JSON array"):
        parse_budget_data('{"fiscal_year": 2026}')


# --- validate_year_entry ---

def test_validate_requires_fiscal_year():
    with pytest.raises(ValueError, match="fiscal_year"):
        validate_year_entry({"line_items": []})


def test_validate_fiscal_year_must_be_int():
    with pytest.raises(ValueError, match="integer"):
        validate_year_entry({"fiscal_year": "2026"})


def test_validate_valid_entry():
    validate_year_entry({"fiscal_year": 2026, "line_items": [], "capital_projects": []})


# --- upsert_line_items ---

def test_upsert_line_items_executes_per_item():
    session = MagicMock()
    items = [
        {"gl_number": "1100-4140-0000-1100-0000", "fund_code": "1100",
         "fund_name": "General Fund", "department": "City Clerk",
         "description": "FULL TIME WAGES", "prior_year_amended": 463070.00,
         "year_requested": 518350.00, "year_approved": 518350.00},
        {"gl_number": "1100-4140-0000-1200-0000", "fund_code": "1100",
         "fund_name": "General Fund", "department": "City Clerk",
         "description": "PART TIME WAGES", "prior_year_amended": 84270.00,
         "year_requested": 44380.00, "year_approved": 44380.00},
    ]
    count = upsert_line_items(session, 2026, items)
    assert count == 2
    assert session.execute.call_count == 2


def test_upsert_line_items_noop_on_empty():
    session = MagicMock()
    count = upsert_line_items(session, 2026, [])
    assert count == 0
    session.execute.assert_not_called()


# --- upsert_capital_projects ---

def test_upsert_capital_projects_executes_per_project():
    session = MagicMock()
    projects = [
        {"gl_number": "1455-3359-4312-2009-7208-1455", "project_name": "TRUES BROOK BRIDGE",
         "fund_code": "1455", "fund_name": "CIP",
         "year_requested": 228070.00, "year_approved": 228070.00},
    ]
    count = upsert_capital_projects(session, 2026, projects)
    assert count == 1
    session.execute.assert_called_once()


def test_upsert_capital_projects_noop_on_empty():
    session = MagicMock()
    count = upsert_capital_projects(session, 2026, [])
    assert count == 0
    session.execute.assert_not_called()
