# City budgets: tasks

**Status:** Done
**Created:** 2026-06-07
**Updated:** 2026-10-16

- [x] 1. Add budget tables
  - Add the `BudgetDocument`, `BudgetLineItem`, and `BudgetCapitalProject` ORM models and export them from `postgres.models`.
  - Add migration `j0k1l2m3n4o5_add_budget_tables.py`, revising `i9j0k1l2m3n4`, with the three unique constraints and three indexes.
  - Make the downgrade drop the indexes, then the tables.
  - _Requirements: 2.1, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 2. Build the discovery spider
  - [x] 2.1 Add the `BudgetDocumentRecord` Pydantic model and the `BudgetDocumentItem` Scrapy item, and export both.
  - [x] 2.2 Parse the index page for year links, skipping the index link and repeats.
  - [x] 2.3 Parse each year page for the fiscal year and the two DocumentCenter PDF links, checking "line item" before "budget".
  - Test both parse methods against `HtmlResponse` fixtures in `scrapers/tests/test_budget_discovery_spider.py`.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11_

- [x] 3. Store discovered documents
  - Add `BudgetDocumentPipeline`, which validates each item and upserts on `uq_budget_document_year_type`, updating only the URL and scrape time.
  - Pass other items through, roll back on error, and commit when the spider closes.
  - Register the pipeline in `scrapers/settings.py` at priority 700.
  - Test pass-through, one execute per item, and commit on close with a mock session in `scrapers/tests/test_budget_pipeline.py`.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 4. Schedule discovery
  - Add the `budget_discovery` DAG in `dags/scrape/budget_discovery.py`, monthly on the 1st at 04:00 UTC, no catchup, one retry after 5 minutes.
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 5. Download PDFs and extract text
  - Add `scripts/scrape/download_budget_pdfs.py` with `output_path`, `extract_text`, `download_pdf`, and `main`.
  - Process pending rows one at a time and commit `text_extracted` after each file is written.
  - Test `output_path` names and `extract_text` on one- and two-page PDFs in `scripts/tests/test_budget_scripts.py`.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

- [x] 6. Keep generated files out of git
  - Add `.gitignore` rules for budget PDFs, text files, and `budget_data.json`.
  - Add `scripts/data/budgets/.gitkeep`.
  - _Requirements: 8.1, 8.2_

- [x] 7. Define the agent handoff format
  - Document the `budget_data.json` format and the extraction rules for the external agent in the design.
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 8. Import structured budget data
  - [x] 8.1 Add `parse_budget_data`, which strips code fences and rejects bad JSON and non-arrays.
  - [x] 8.2 Add `validate_year_entry` for a missing or non-integer `fiscal_year`.
  - [x] 8.3 Add `upsert_line_items` and `upsert_capital_projects`, keyed on fiscal year and GL number, with no writes for an empty list.
  - [x] 8.4 Add `main`, which fails when the file is missing and commits and logs one fiscal year at a time.
  - Test each function in `scripts/tests/test_budget_scripts.py`.
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12, 6.13_
