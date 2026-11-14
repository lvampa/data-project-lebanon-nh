# City budgets: design

**Status:** Done
**Created:** 2026-06-07
**Updated:** 2026-11-14

## Overview

Four steps run on their own and hand off through the database or files.
A Scrapy spider finds the Budget Book and Line Items PDF for each fiscal year and records them in `budget_documents`.
A download script fetches pending PDFs and writes their text to disk with `pypdf`.
An external Claude Code agent reads the text and writes one JSON handoff file.
An import script validates that file and upserts it into `budget_line_items` and `budget_capital_projects`.
Generated files stay out of git.
The PDFs from 2016 to 2026 extract cleanly with `pypdf`, so no OCR is needed.

## Data flow

```
lebanonnh.gov index page
  -> budget_discovery spider (monthly DAG) -> BudgetDocumentPipeline -> budget_documents
  -> scripts/scrape/download_budget_pdfs.py -> scripts/data/budgets/{year}-{type}.pdf and .txt
  -> Claude Code agent (outside this repo)   -> budget_data.json
  -> scripts/ingest/import_budget_data.py    -> budget_line_items, budget_capital_projects
```

- **Discovery:** the spider follows the budget links on the index page, reads the fiscal year from each year page URL, and matches link text to a document type.
  "Line item" is checked before "budget", because "Line Item Budget" contains both words.
  The pipeline validates each item and upserts on `(fiscal_year, document_type)`, updating only `source_url` and `scraped_at`.
- **Schedule:** the `budget_discovery` DAG runs on the 1st of every month, because the publish date varies.
  The pipeline is idempotent, so extra runs cost nothing.
- **Download:** the script handles documents with `text_extracted` false, one at a time, and commits after each.
  A failure stops the run and leaves the rest pending.
- **Extraction agent:** it reads the `.txt` files and writes one JSON array, one object per fiscal year, with `line_items` and `capital_projects`.
  It skips "Total Department" subtotal rows, takes the department from the section heading, and takes the fund name from the fund code in the GL number.
- **Import:** the script strips an optional Markdown fence, checks that each year entry has an integer `fiscal_year`, and upserts one year at a time.

## Data model

- `budget_documents`: unique on `(fiscal_year, document_type)`, with `source_url`, `text_extracted` and `scraped_at`.
- `budget_line_items`: unique on `(fiscal_year, gl_number)`, with fund code and name, department, description, and three amounts (prior year amended, requested, approved).
- `budget_capital_projects`: unique on `(fiscal_year, gl_number)`, with project name, fund and two amounts.
- GL numbers look like `FFFF-GGGG-SSSS-TTTT-CCCC`; the first four digits are the fund code (1100 General Fund, 2108 Solid Waste, 2110 Water, 2115 Wastewater, 2120 Airport, 1455 to 1477 capital and airport projects).
- Department totals come from a `GROUP BY` query, not a table.

## Failure handling

- A year page with no fiscal year in its URL, or a link that matches no document type, is skipped with a warning.
- A missing handoff file stops the import with a message to run the agent first; bad JSON stops it before any write.
- A line item missing a required key fails that year's import, and earlier years stay committed.

## Decisions

- **Separate discovery, download, extraction and import.**
  Each step can be re-run alone, and the AI step stays outside the codebase.
  Rejected: one end-to-end job, because a bad extraction would force a fresh download.
- **File handoff to an external agent.**
  It matches incident type categorization and keeps the agent on a subscription plan instead of the billed API.
- **No URL queue.**
  About 20 PDFs do not justify the queue the police log spiders use.
- **Department totals by query.**
  A totals table would duplicate what a `GROUP BY` returns.
- **Shared data directory.**
  The handoff scripts all use `scripts/data/`, so the files line up and stay covered by `.gitignore`.
  `scripts/tests/test_data_paths.py` guards this.
- **Light import validation.**
  Only `fiscal_year` is checked.
  Rejected: validating GL number patterns and amount types, which the database already enforces.
- **Tax mill rate deferred.**
  The text only mentions percentage changes; the real rate needs the NH Department of Revenue Administration or the cover page.

## Open questions

- When a PDF's URL changes, the pipeline updates `source_url` but keeps `text_extracted` true, so the new file is never fetched.
  Resetting `text_extracted` on a URL change would fix it.
