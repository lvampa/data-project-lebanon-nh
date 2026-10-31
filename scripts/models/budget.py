from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class BudgetLineItemRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    gl_number: str = Field(min_length=1)
    fund_code: str = Field(min_length=1)
    fund_name: str = Field(min_length=1)
    department: str = Field(min_length=1)
    description: str = Field(min_length=1)
    prior_year_amended: Decimal | None = None
    year_requested: Decimal | None = None
    year_approved: Decimal | None = None


class BudgetCapitalProjectRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    gl_number: str = Field(min_length=1)
    project_name: str = Field(min_length=1)
    fund_code: str = Field(min_length=1)
    fund_name: str = Field(min_length=1)
    year_requested: Decimal | None = None
    year_approved: Decimal | None = None


class BudgetYearRecord(BaseModel):
    # The agent writes years as JSON numbers; a string year means it went off
    # script, so reject it instead of coercing.
    fiscal_year: StrictInt
    line_items: list[BudgetLineItemRecord] = []
    capital_projects: list[BudgetCapitalProjectRecord] = []
