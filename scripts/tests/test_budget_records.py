from decimal import Decimal

import pytest
from pydantic import ValidationError

from scripts.models import (
    BudgetCapitalProjectRecord,
    BudgetLineItemRecord,
    BudgetYearRecord,
)

LINE_ITEM = {
    "gl_number": "1100-4140-0000-1100-0000",
    "fund_code": "1100",
    "fund_name": "General Fund",
    "department": "City Clerk",
    "description": "FULL TIME WAGES",
    "prior_year_amended": 463070.00,
    "year_requested": 518350.00,
    "year_approved": None,
}

CAPITAL_PROJECT = {
    "gl_number": "1455-3359-4312-2009-7208-1455",
    "project_name": "TRUES BROOK BRIDGE",
    "fund_code": "1455",
    "fund_name": "CIP",
    "year_requested": 228070.00,
}


def test_line_item_accepts_agent_output():
    record = BudgetLineItemRecord.model_validate(LINE_ITEM)
    assert record.prior_year_amended == Decimal("463070")
    assert record.year_approved is None


def test_line_item_requires_gl_number():
    with pytest.raises(ValidationError, match="gl_number"):
        BudgetLineItemRecord.model_validate({**LINE_ITEM, "gl_number": " "})


def test_line_item_rejects_non_numeric_amount():
    with pytest.raises(ValidationError, match="year_requested"):
        BudgetLineItemRecord.model_validate({**LINE_ITEM, "year_requested": "lots"})


def test_capital_project_defaults_missing_amounts_to_none():
    record = BudgetCapitalProjectRecord.model_validate(CAPITAL_PROJECT)
    assert record.year_approved is None


def test_capital_project_requires_project_name():
    project = {k: v for k, v in CAPITAL_PROJECT.items() if k != "project_name"}
    with pytest.raises(ValidationError, match="project_name"):
        BudgetCapitalProjectRecord.model_validate(project)


def test_year_accepts_nested_items():
    year = BudgetYearRecord.model_validate(
        {
            "fiscal_year": 2026,
            "line_items": [LINE_ITEM],
            "capital_projects": [CAPITAL_PROJECT],
        }
    )
    assert year.line_items[0].department == "City Clerk"
    assert year.capital_projects[0].fund_code == "1455"


def test_year_defaults_to_no_items():
    year = BudgetYearRecord.model_validate({"fiscal_year": 2026})
    assert year.line_items == []
    assert year.capital_projects == []


def test_year_rejects_string_fiscal_year():
    with pytest.raises(ValidationError, match="integer"):
        BudgetYearRecord.model_validate({"fiscal_year": "2026"})
