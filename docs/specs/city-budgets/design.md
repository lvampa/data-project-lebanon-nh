# City budgets: design

**Status:** Done
**Created:** 2026-06-07
**Updated:** 2026-10-16

## Overview

The feature is four steps that each run on their own and hand off through the database or files.
A Scrapy spider finds the Budget Book and Line Items PDF for each year and records them in `budget_documents` (Requirements 1, 2, 3).
A download script fetches pending PDFs and writes their text to disk with `pypdf` (Requirement 4).
An external Claude Code agent reads the text and writes one JSON handoff file (Requirement 5).
An import script validates that file and upserts it into `budget_line_items` and `budget_capital_projects` (Requirements 6, 7).
Generated files stay out of git (Requirement 8).

The PDFs from 2016 to 2026 extract cleanly with `pypdf`, so no OCR is needed.

## Architecture

```
lebanonnh.gov index page
        |
        v
budget_discovery spider --> BudgetDocumentPipeline --> budget_documents
  (Airflow DAG, monthly)                                    |
                                                            v
                                          download_budget_pdfs.py
                                                            |
                                                            v
                                   budgets/{year}-{type}.pdf and .txt
                                                            |
                                                            v
                                     Claude Code agent (external)
                                                            |
                                                            v
                                                   budget_data.json
                                                            |
                                                            v
                                           import_budget_data.py
                                                            |
                                                            v
                              budget_line_items, budget_capital_projects
```

There is no MongoDB URL queue for this spider.
There are only about 20 PDFs in total, so the queue pattern used by other scrapers adds nothing.

Operator workflow:

```bash
# 1. Discover PDFs. The DAG also runs this monthly.
cd scrapers && uv run scrapy crawl budget_discovery

# 2. Download and extract text.
uv run python scripts/scrape/download_budget_pdfs.py

# 3. Run the Claude Code agent, set up outside this repo.
#    Reads the .txt files and writes budget_data.json.

# 4. Import.
uv run python scripts/ingest/import_budget_data.py
```

## Components and interfaces

### Discovery spider

Lives in `scrapers/spiders/budget_discovery.py`, with the item in `scrapers/items/budget.py`.

- `BudgetDiscoverySpider`, name `budget_discovery`, allowed domains `www.lebanonnh.gov` and `lebanonnh.gov`.
- `parse(response)` reads the index page, selects `#main-content a[href*='Budget']` and `.field-items a[href*='Budget']`, skips empty, repeated, and `/852/` links, and follows the rest to `parse_year_page` (1.1 to 1.4).
- `parse_year_page(response)` reads the fiscal year from the URL with `/(20\d{2})[/-]` (1.5, 1.6).
  It then checks each `a[href*='DocumentCenter']` link's text against an ordered list of patterns (1.7 to 1.11).
  `line.?item` is checked first and maps to `line_items`, then `budget` maps to `budget_book`.
  The order matters because "Line Item Budget" contains both words.
- Output is one `BudgetDocumentItem` per PDF:

```python
class BudgetDocumentItem(scrapy.Item):
    fiscal_year = scrapy.Field()    # int
    document_type = scrapy.Field()  # 'budget_book' | 'line_items'
    source_url = scrapy.Field()     # absolute URL
    scraped_at = scrapy.Field()     # naive UTC datetime
```

### Document pipeline

`BudgetDocumentPipeline` lives in `scrapers/pipelines.py` and is registered in `scrapers/settings.py` at priority 700.

- Ignores items that are not `BudgetDocumentItem` and returns them unchanged (2.4).
- Validates each item with the Pydantic model `BudgetDocumentRecord` in `scrapers/models/budget_document.py` (2.5).
  The model strips whitespace, requires an integer `fiscal_year`, and requires non-empty `document_type` and `source_url`.
- Inserts into `budget_documents` with `ON CONFLICT ON CONSTRAINT uq_budget_document_year_type DO UPDATE`, setting only `source_url` and `scraped_at` (2.1 to 2.3).
- Rolls back and re-raises on a write error (2.6), and commits once when the spider closes (2.7).

### Airflow DAG

Lives in `dags/scrape/budget_discovery.py` (3.1 to 3.3).

- `dag_id="budget_discovery"`, `schedule="0 4 1 * *"`, start date 2026-06-01 UTC, `catchup=False`, tag `budget`.
- One `BashOperator` runs `cd /opt/project/scrapers && uv run --frozen scrapy crawl budget_discovery` with `retries=1` and `retry_delay=5 minutes`.

### Download script

Lives in `scripts/scrape/download_budget_pdfs.py` (Requirement 4).

```python
def output_path(fiscal_year: int, document_type: str) -> Path: ...  # DATA_DIR / f"{fiscal_year}-{document_type}.txt"
def extract_text(pdf_path: Path) -> str: ...                        # pages joined by "\n", None pages as ""
def download_pdf(url: str, dest: Path) -> None: ...                 # urllib.request.urlretrieve
def main() -> None: ...
```

`main` selects rows where `text_extracted` is false and handles them one at a time.
For each row it downloads the PDF, extracts and writes the text, sets `text_extracted`, and commits.

### Extraction agent

External to this repo, set up by the operator, using the same file handoff pattern as incident type categorization (Requirement 5).
It reads every `.txt` file in the budgets data directory and writes the handoff file in the format under Data models.
Its instructions:

- Skip "Total Department" subtotal rows and extract only GL-numbered rows.
- Take `department` from the section heading above the rows, like "CITY CLERK".
- Take `fund_name` from the fund code, using the table under Data models.
- Take capital projects from the CIP and AIP sections, with the description as `project_name` and the GL number as the key.
- Write one array that covers every year in the input directory.

### Import script

Lives in `scripts/ingest/import_budget_data.py` (Requirement 6).

```python
def parse_budget_data(text: str) -> list[dict]: ...  # strips ``` fences, raises ValueError on bad JSON or non-array
def validate_year_entry(entry: dict) -> None: ...    # raises ValueError if fiscal_year is missing or not int
def upsert_line_items(session, fiscal_year: int, items: list[dict]) -> int: ...
def upsert_capital_projects(session, fiscal_year: int, projects: list[dict]) -> int: ...
def main() -> None: ...
```

Both upsert functions run one `INSERT ... ON CONFLICT DO UPDATE` per row and return the row count.
They return 0 without touching the session for an empty list.
`main` validates, upserts, and commits one fiscal year at a time.

## Data models

### Source formats

Line rows in the Line Items PDF have three amounts: prior year amended, current year requested, and current year approved.

```
1100-4140-0000-1100-0000 FULL TIME WAGES  463,070.00  518,350.00  518,350.00
Total Department CITY CLERK: 822,670.00 822,670.00 822,670.00
```

Capital project rows carry the project name in the description and have two amounts.

```
1455-3359-4312-2009-7208-1455 TRUES BROOK BRIDGE #066-059  228,070  228,070
1475-3319-0010-2026-7301-1475 T HANGAR CONSTRUCTION  3,570,530  3,570,530
```

GL numbers have the form `FFFF-GGGG-SSSS-TTTT-CCCC`, and the first four digits are the fund code.

| Fund code | Fund |
|-----------|------|
| 1100 | General Fund |
| 2108 | Solid Waste |
| 2110 | Water |
| 2115 | Wastewater |
| 2120 | Airport |
| 1455 to 1477 | Capital and Airport Improvement Projects |

### Tables

All three tables come from one Alembic migration, `shared/postgres/migrations/versions/j0k1l2m3n4o5_add_budget_tables.py`, which revises `i9j0k1l2m3n4`.
The ORM models are in `shared/postgres/src/postgres/models/` as `BudgetDocument`, `BudgetLineItem`, and `BudgetCapitalProject`.

`budget_documents`:

```
id              serial PK
fiscal_year     integer NOT NULL
document_type   text NOT NULL            -- 'budget_book' | 'line_items'
source_url      text NOT NULL
text_extracted  boolean NOT NULL DEFAULT false
scraped_at      timestamp NOT NULL
CONSTRAINT uq_budget_document_year_type UNIQUE (fiscal_year, document_type)
```

`budget_line_items`:

```
id                  serial PK
fiscal_year         integer NOT NULL
gl_number           text NOT NULL        -- '1100-4140-0000-1100-0000'
fund_code           text NOT NULL        -- '1100'
fund_name           text NOT NULL        -- 'General Fund'
department          text NOT NULL        -- 'City Clerk'
description         text NOT NULL        -- 'FULL TIME WAGES'
prior_year_amended  numeric(14,2)
year_requested      numeric(14,2)
year_approved       numeric(14,2)
CONSTRAINT uq_budget_line_item_year_gl UNIQUE (fiscal_year, gl_number)
INDEX idx_budget_line_items_year_dept (fiscal_year, department)
INDEX idx_budget_line_items_year_fund (fiscal_year, fund_code)
```

`budget_capital_projects`:

```
id              serial PK
fiscal_year     integer NOT NULL
gl_number       text NOT NULL
project_name    text NOT NULL
fund_code       text NOT NULL            -- '1455' (CIP) or '1475' to '1477' (AIP)
fund_name       text NOT NULL
year_requested  numeric(14,2)
year_approved   numeric(14,2)
CONSTRAINT uq_budget_capital_project_year_gl UNIQUE (fiscal_year, gl_number)
INDEX idx_budget_capital_projects_year (fiscal_year)
```

Department totals come from a query, not a table (7.5):

```sql
SELECT fiscal_year, fund_code, department, SUM(year_approved) AS total
FROM budget_line_items
GROUP BY fiscal_year, fund_code, department;
```

Both data tables are also indexed into Elasticsearch by `scripts/sync/sync_es.py` and searchable through `api/routers/search.py`.
That is part of the search feature, not this one.

### Files

Text files are named `{fiscal_year}-{document_type}.txt`, like `2026-budget_book.txt`, next to the PDF of the same name.

The handoff file is a JSON array with one object per fiscal year:

```json
[
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
        "project_name": "TRUES BROOK BRIDGE #066-059",
        "fund_code": "1455",
        "fund_name": "CIP",
        "year_requested": 228070.00,
        "year_approved": 228070.00
      }
    ]
  }
]
```

`gl_number`, `fund_code`, `fund_name`, `description`, `department`, and `project_name` are required on their rows.
Amount fields are optional and become null when missing.
The file may be wrapped in a Markdown code fence.

`.gitignore` covers these paths (Requirement 8):

```
scripts/data/budgets/*.pdf
scripts/data/budgets/*.txt
scripts/data/budget_data.json
```

## Error handling

| Failure | Result |
|---|---|
| Year page URL has no fiscal year. | The spider logs a warning and yields nothing for that page. |
| Link text matches no document type. | The link is skipped. |
| Item fails `BudgetDocumentRecord` validation. | Pydantic raises before any write, and Scrapy drops the item. |
| Database error in the pipeline. | The session rolls back and the error is raised. |
| Crawl task fails in Airflow. | One retry after 5 minutes. |
| No pending documents. | The download script logs it and exits. |
| Download or extraction error. | The script stops. Documents already done stay committed, and the rest stay pending for the next run. |
| Handoff file missing. | `FileNotFoundError` telling the operator to run the agent first. |
| Handoff file is not JSON or not an array. | `ValueError` before any write. |
| Year entry missing `fiscal_year` or with a non-integer one. | `ValueError` on that entry. Earlier years stay committed. |
| Line item or project missing a required key. | `KeyError`, and that year's uncommitted rows are not saved. |

## Testing strategy

Unit tests only, with no live HTTP or database in the automated suite.

- `scrapers/tests/test_budget_discovery_spider.py` builds `HtmlResponse` fixtures for an index page and a year page.
  It checks that year links are followed and the index link is not, that two items come back with the right year and types, and that non-DocumentCenter links are skipped.
- `scrapers/tests/test_budget_pipeline.py` uses a mock session.
  It checks that other items pass through untouched, that a budget item runs one execute, and that closing commits and closes the session.
- `scripts/tests/test_budget_scripts.py` covers the pure functions.
  For download, it checks `output_path` names and that `extract_text` returns a string for one- and two-page blank PDFs.
  For import, it checks `parse_budget_data` on valid, fenced, empty, invalid, and non-array input.
  It also checks `validate_year_entry` on missing, string, and valid years, and the upsert functions' counts and empty no-ops.

Left untested: the migration, the DAG, `download_pdf`, both `main` functions, the SQL the upserts produce, and the extraction agent's output quality.

## Decisions

- **Separate discovery, download, extraction, and import.**
  Each step can be re-run alone, and the AI step stays outside the codebase.
  A single end-to-end job was rejected because a bad extraction would force a fresh download.
- **File handoff to an external agent.**
  This matches incident type categorization and keeps the agent on the Max plan instead of the billed API.
- **No URL queue.**
  About 20 PDFs do not justify the MongoDB queue other spiders use.
- **Department totals by query.**
  A totals table would duplicate data that a `GROUP BY` returns.
- **Tax mill rate deferred.**
  The text only mentions percentage changes, and the real rate needs the NH DRA or the cover page.

Divergences from the original design and plan:

- **Monthly schedule, not annual in July.**
  The DAG runs on the first of every month because the publish date varies.
  The pipeline is idempotent, so extra runs cost nothing.
- **DAG location.**
  The plan put the DAG in `scrapers/dags/`.
  All DAGs moved to the top-level `dags/` folder, and this one is now `dags/scrape/budget_discovery.py`.
- **Script locations.**
  The scripts moved from `scripts/` into `scripts/scrape/` and `scripts/ingest/` in a later reorganization.
  Their docstrings still show the old `scripts/<name>.py` run commands.
- **Lighter import validation.**
  The design called for checking GL numbers against a pattern and checking that amounts are numeric.
  The import script only checks `fiscal_year`.
  Missing required keys fail with `KeyError`, and wrong amount types fail at the database.
- **`urllib` instead of `httpx`.**
  The download script uses `urllib.request.urlretrieve`, so it needs no extra dependency.
- **Pydantic validation in the pipeline.**
  The plan added `BudgetDocumentRecord` to match the other pipelines, which the design did not mention.
- **Shared data directory.**
  After the scripts moved into subfolders, each resolved its own `data/` folder, which broke the handoff and fell outside `.gitignore`.
  All handoff scripts now use `Path(__file__).parents[1] / "data"`, so they share `scripts/data/`.
  `scripts/tests/test_data_paths.py` guards this.

## Open questions

- **Changed URLs are not re-downloaded.**
  When a PDF's URL changes, the pipeline updates `source_url` but keeps `text_extracted` true, so the new file is never fetched.
  Resetting `text_extracted` on a URL change would fix it.
