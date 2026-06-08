from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BudgetDocumentRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    fiscal_year: int
    document_type: str = Field(min_length=1)  # 'budget_book' | 'line_items'
    source_url: str = Field(min_length=1)
    scraped_at: datetime
