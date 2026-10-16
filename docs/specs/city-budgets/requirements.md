# City budgets: requirements

**Status:** Done
**Created:** 2026-06-07
**Updated:** 2026-10-16

## Introduction

Lebanon NH publishes each approved city budget as PDFs, which makes year-over-year comparison slow and manual.
Real estate investors and civic researchers want to see how spending changes by department, by fund, and on capital projects.
Success means the approved budgets from 2016 to 2026 live in Postgres as line items and capital projects, and new budgets are found without manual checks.

## Glossary

- **Index page:** The city page that links to each year's approved budget, at `https://www.lebanonnh.gov/852/Approved-City-Budgets`.
- **Year page:** The page for one fiscal year's approved budget, linked from the index page.
- **Budget Book:** The full budget PDF for a year, about 120 pages of narrative and line items.
- **Line Items PDF:** The line-item-only PDF for a year, about 50 pages covering all funds.
- **Document type:** Either `budget_book` or `line_items`.
- **GL number:** The general ledger account number on each row, like `1100-4140-0000-1100-0000`.
- **Fund code:** The first four digits of a GL number, like `1100` for the General Fund.
- **Line item:** One GL-numbered row in the budget, with prior year amended, requested, and approved amounts.
- **Capital project:** One GL-numbered row in the CIP or AIP section, with a project name and requested and approved amounts.
- **Handoff file:** `budget_data.json`, the structured data an external Claude Code agent writes from the extracted text.

## Requirements

### Requirement 1: Discover budget PDFs

**User story:** As an operator, I want new budget PDFs found automatically, so that the data stays current without manual checks.

#### Acceptance criteria

1. WHEN the discovery spider runs, THE spider SHALL request the index page.
2. WHEN the spider parses the index page, THE spider SHALL follow each link in the main content whose URL contains `Budget`.
3. IF an index page link points back to the index page, THEN THE spider SHALL skip it.
4. IF the index page repeats a link, THEN THE spider SHALL follow it only once.
5. WHEN the spider parses a year page, THE spider SHALL take the fiscal year from the four-digit `20xx` year in the page URL.
6. IF a year page URL has no fiscal year, THEN THE spider SHALL log a warning and record no documents from that page.
7. WHEN a year page links to a DocumentCenter file whose link text matches "line item", THE spider SHALL record it with document type `line_items`.
8. WHEN a year page links to a DocumentCenter file whose link text contains "budget" and does not match "line item", THE spider SHALL record it with document type `budget_book`.
9. IF a year page link does not point to DocumentCenter, THEN THE spider SHALL skip it.
10. IF a DocumentCenter link's text matches neither document type, THEN THE spider SHALL skip it.
11. THE spider SHALL record each document's URL as an absolute URL.

### Requirement 2: Store discovered documents

**User story:** As an operator, I want each discovered PDF recorded once, so that re-running discovery does not create duplicates.

#### Acceptance criteria

1. WHEN the pipeline receives a budget document, THE pipeline SHALL add a `budget_documents` row with `text_extracted` set to false.
2. IF a row for that fiscal year and document type already exists, THEN THE pipeline SHALL update its source URL and scrape time instead of adding a duplicate.
3. IF a row for that fiscal year and document type already exists, THEN THE pipeline SHALL leave its `text_extracted` value unchanged.
4. WHEN the pipeline receives an item that is not a budget document, THE pipeline SHALL pass it on unchanged without writing to `budget_documents`.
5. IF a budget document has no fiscal year, an empty document type, or an empty source URL, THEN THE pipeline SHALL reject it without writing a row.
6. IF the database write fails, THEN THE pipeline SHALL roll back the session and raise the error.
7. WHEN the spider closes, THE pipeline SHALL commit and close its database session.

### Requirement 3: Run discovery on a schedule

**User story:** As an operator, I want discovery to run by itself, so that a new budget shows up without me starting a crawl.

#### Acceptance criteria

1. THE Airflow DAG `budget_discovery` SHALL run the discovery spider at 04:00 UTC on the first day of every month.
2. THE DAG SHALL not run for schedule intervals that passed before it was enabled.
3. IF the crawl task fails, THEN THE DAG SHALL retry it once after 5 minutes.

### Requirement 4: Download PDFs and extract text

**User story:** As an operator, I want each PDF saved as plain text, so that the extraction agent can read it without handling PDFs.

#### Acceptance criteria

1. WHEN the download script runs, THE script SHALL process every `budget_documents` row whose `text_extracted` is false.
2. IF no rows have `text_extracted` false, THEN THE script SHALL log that all documents are extracted and exit without downloading anything.
3. WHEN the script processes a row, THE script SHALL save the PDF as `{fiscal_year}-{document_type}.pdf` in the budgets data directory.
4. WHEN the script processes a row, THE script SHALL write the text of every page, joined by newlines, to `{fiscal_year}-{document_type}.txt` in the budgets data directory.
5. IF a PDF page has no extractable text, THEN THE script SHALL treat that page as empty and continue.
6. WHEN a document's text file is written, THE script SHALL set its `text_extracted` to true and commit before moving to the next document.
7. IF a download or extraction fails, THEN THE script SHALL stop and leave that document and any later ones with `text_extracted` false, so the next run retries them.
8. IF the budgets data directory does not exist, THEN THE script SHALL create it.

### Requirement 5: Hand off structured data in a fixed format

**User story:** As an operator, I want the extraction agent to write one JSON file in a known shape, so that the import script can load it without guessing.

#### Acceptance criteria

1. THE handoff file SHALL be a JSON array with one object per fiscal year, each holding `fiscal_year`, `line_items`, and `capital_projects`.
2. THE extraction agent SHALL leave out "Total Department" subtotal rows and record only GL-numbered rows.
3. THE extraction agent SHALL take each line item's department from the section heading above it.
4. THE extraction agent SHALL take each row's fund name from its fund code.
5. THE extraction agent SHALL record rows from the CIP and AIP sections as capital projects, using the row description as the project name.
6. THE extraction agent SHALL cover every fiscal year found in the extracted text files in one array.

### Requirement 6: Import structured budget data

**User story:** As an operator, I want the handoff file loaded into Postgres safely, so that I can re-run the import after fixing the data.

#### Acceptance criteria

1. WHEN the import script runs, THE script SHALL read the handoff file.
2. IF the handoff file does not exist, THEN THE script SHALL fail with an error that says to run the extraction agent first.
3. WHEN the handoff file is wrapped in Markdown code fences, THE script SHALL strip the fences before parsing.
4. IF the handoff file is not valid JSON, THEN THE script SHALL fail with an error that includes the first 200 characters of the input.
5. IF the handoff file's top-level value is not an array, THEN THE script SHALL fail with an error naming the type it found.
6. IF the handoff file is an empty array, THEN THE script SHALL exit without writing any rows.
7. IF a year entry has no `fiscal_year`, or its `fiscal_year` is not an integer, THEN THE script SHALL fail on that entry and keep the years already committed.
8. WHEN a year entry is valid, THE script SHALL insert or update each line item keyed on fiscal year and GL number.
9. WHEN a year entry is valid, THE script SHALL insert or update each capital project keyed on fiscal year and GL number.
10. IF a year entry's `line_items` or `capital_projects` is missing or empty, THEN THE script SHALL skip that list without database writes.
11. IF a line item or capital project has no value for an amount, THEN THE script SHALL store that amount as null.
12. WHEN a fiscal year's rows are written, THE script SHALL commit that year and log the count of line items and capital projects.
13. WHEN the script runs twice on the same handoff file, THE script SHALL leave the same rows in the database as after the first run.

### Requirement 7: Query spending by year, department, fund, and project

**User story:** As an analyst, I want budget data in tables I can group and sum, so that I can compare spending across years.

#### Acceptance criteria

1. THE `budget_line_items` table SHALL hold at most one row per fiscal year and GL number.
2. THE `budget_capital_projects` table SHALL hold at most one row per fiscal year and GL number.
3. THE `budget_documents` table SHALL hold at most one row per fiscal year and document type.
4. THE budget tables SHALL store amounts to the cent, with up to 12 digits before the decimal point.
5. WHEN an analyst sums `year_approved` grouped by fiscal year, fund code, and department, THE database SHALL return department totals without a separate totals table.

### Requirement 8: Keep generated files out of git

**User story:** As a developer, I want downloaded PDFs and generated data kept out of the repository, so that the repo stays small and holds no derived data.

#### Acceptance criteria

1. THE repository SHALL ignore budget PDFs, extracted text files, and the handoff file.
2. THE repository SHALL track the empty budgets data directory with a `.gitkeep` file.

## Out of scope

- Tax mill rate. The PDFs have no reliable single number for it.
- A frontend budget explorer.
- Stored year-over-year differences. They are derived by query.
- Budget narrative and summary text.
- Budgets from before 2016.
- Running the extraction agent. It is set up and run outside this repo.
