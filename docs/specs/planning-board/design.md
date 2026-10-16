# Planning board: design

**Status:** Done
**Created:** 2026-06-03
**Updated:** 2026-10-16

## Overview

A standalone Playwright script calls the public CivicClerk OData API from inside a real Chromium context, because the WAF returns 404 to plain HTTP clients.
It finds the Planning Board category, pages through its events with published files expanded, downloads each file, extracts PDF text with pypdf, and upserts meetings and documents into two PostgreSQL tables.
A daily Airflow DAG runs the script.
This covers requirements 1 through 5.

## Architecture

```
Airflow DAG civicclerk_planning (daily 05:00 UTC)
  -> BashOperator: uv run python scripts/scrape/scrape_civicclerk.py
       -> Chromium: load portal home page (cookies, headers)
       -> context.request GET /v1/EventCategories        -> pick "planning" category
       -> context.request GET /v1/Events?$filter=...      -> pages of 100 events + publishedFiles
       -> for each event:
            upsert planning_meetings
            for each published file:
              GET download URL -> pypdf text -> upsert planning_documents
       -> one commit for the whole run
```

The script follows the same pattern as `scripts/scrape/scrape_llcs.py`.
Downstream, `scripts/sync/sync_es.py` reads both tables into the Elasticsearch search index, which is outside this spec.

## Components and interfaces

### Scraper script

Lives in `scripts/scrape/scrape_civicclerk.py`.
Run with `uv run python scripts/scrape/scrape_civicclerk.py [--limit N]`, where `N=0` (the default) means all events.

Pure functions, unit tested:

```python
def parse_event(data: dict, category_name: str) -> dict: ...
# -> civicclerk_event_id, title, category, meeting_date, location, status, source_url

def parse_file(data: dict, event_id: int) -> dict: ...
# -> civicclerk_file_id, civicclerk_event_id, file_name, file_type, download_url

def extract_text_from_pdf(data: bytes) -> str | None: ...
```

Network functions, which take the Playwright `APIRequestContext`:

```python
async def fetch_planning_category_id(request_ctx) -> tuple[int, str]: ...
async def fetch_events(request_ctx, group_id: int, limit: int) -> list[dict]: ...
async def run(limit: int) -> None: ...
```

`run` sets `scraped_at` to one naive UTC timestamp shared by every row in the run.
It logs spans and counts to Logfire.

### CivicClerk API

Base URL `https://lebanonh.api.civicclerk.com/v1`, OData v4, no auth (security NONE per `/swagger/v1/swagger.json`).

| Call | Purpose |
|---|---|
| `GET /EventCategories` | List categories. Response is `{"value": [...]}` or a bare list. |
| `GET /Events?$filter=eventGroupId eq {id}&$top=100&$skip={n}&$orderby=eventStartDate desc&$expand=publishedFiles` | One page of events. |
| `GET /Events/GetEventFileStream(fileId={id},fileType={type},plainText=false)` | File bytes, used when `streamUrl` is null. |

Event fields used:

```
id                integer
title             string
eventStartDate    string (ISO 8601)
location          string
status            { description: string } | null
publishedFiles    array of:
    id            integer
    name          string
    fileType      integer (1=Agenda, 2=Minutes, 3=Attachment)
    streamUrl     string | null
```

### Airflow DAG

Lives in `dags/scrape/civicclerk_planning.py`.

| Setting | Value |
|---|---|
| `dag_id` | `civicclerk_planning` |
| `schedule` | `0 5 * * *` |
| `start_date` | 2026-06-01 UTC |
| `catchup` | `False` |
| `tags` | `["planning"]` |
| Task | `scrape_planning_board`, BashOperator, `cd /opt/project && uv run --frozen python scripts/scrape/scrape_civicclerk.py` |
| Retries | 1, after 5 minutes |

## Data models

ORM models live in `shared/postgres/src/postgres/models/planning_meeting.py` and `planning_document.py`, and are exported from `postgres.models`.
Migration `k1l2m3n4o5p6_add_planning.py` revises `j0k1l2m3n4o5` (budget tables).

### planning_meetings

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | integer | no | Primary key. |
| `civicclerk_event_id` | integer | no | Unique. Upsert key. |
| `title` | text | yes | |
| `category` | text | yes | Category name from CivicClerk. Indexed. |
| `meeting_date` | timestamp | yes | Naive. Indexed. |
| `location` | text | yes | |
| `status` | text | yes | `status.description`. |
| `source_url` | text | no | Portal event page. |
| `scraped_at` | timestamp | no | Naive UTC. |

Indexes: `idx_planning_meetings_meeting_date`, `idx_planning_meetings_category`.

### planning_documents

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | integer | no | Primary key. |
| `civicclerk_file_id` | integer | no | Unique. Upsert key. |
| `civicclerk_event_id` | integer | no | Indexed. Joins to `planning_meetings.civicclerk_event_id`, no foreign key. |
| `file_name` | text | yes | |
| `file_type` | text | yes | "Agenda", "Minutes", "Attachment", or the raw number. |
| `download_url` | text | yes | |
| `raw_text` | text | yes | Extracted PDF text. |
| `scraped_at` | timestamp | no | Naive UTC. |

Index: `idx_planning_documents_event_id`.

Both upserts use `INSERT ... ON CONFLICT (<civicclerk id>) DO UPDATE` and overwrite every column except the key.

## Error handling

| Failure | Behavior |
|---|---|
| Portal home page does not load within 30 s | Playwright raises, the run fails, Airflow retries once. |
| No category name contains "planning" | `RuntimeError` listing the names received. The run fails. |
| Events page returns an empty list | Paging stops. |
| Start date missing or not ISO 8601 | `meeting_date` is null. |
| Status missing or not an object | `status` is null. |
| File download raises | Logfire warning with the file id. Document stored with null `raw_text`. |
| File returns an error page or non-PDF bytes | No `%PDF` signature, so `raw_text` is null. |
| pypdf cannot parse the file | `raw_text` is null. |
| Database write fails | Session rolls back the whole run, the browser closes, and the error propagates. |

Known gaps:

- An API error response for categories or events is parsed as JSON without a status check, so it fails with a parse or key error rather than a clear message.
- A multi-page PDF with no text layer stores newline characters instead of null.
- Meeting dates with a `Z` suffix are stored as UTC wall time; dates without an offset are stored as given.
- All writes go in one transaction, so one bad row discards the whole run.

## Testing strategy

- Unit tests in `scripts/tests/test_scrape_civicclerk.py` cover `parse_event` (all fields, missing status, bad date), `parse_file` (type mapping, built URL, `streamUrl` override), and `extract_text_from_pdf` (non-PDF and empty input).
- No tests for the network functions, the upserts, the migration, or the DAG.
- The plan called for a manual smoke run with `--limit 5` against the live portal and a check of the resulting rows.
  No record of that run exists in the repo.

## Decisions

- **Playwright request context instead of httpx.** The WAF returns 404 to non-browser clients. Loading the portal page first gives the context the cookies and headers it needs.
- **Category found by name at runtime.** A hardcoded `eventGroupId` would break silently if CivicClerk renumbered categories.
- **Store extracted text, not files.** Text is what search needs, and it keeps the database small. The download URL is kept so files can be fetched again.
- **No foreign key from documents to meetings.** Both rows are keyed by CivicClerk ids and written in the same run, so the plain index is enough.
- **Divergence: file locations.** The plan put the script at `scripts/scrape_civicclerk.py` and the DAG at `scrapers/dags/civicclerk_planning.py`. Later reorganizations moved them to `scripts/scrape/scrape_civicclerk.py` and `dags/scrape/civicclerk_planning.py`, and the DAG command and test import follow the new paths.
- **Divergence: migration revision.** The plan used revision `j0k1l2m3n4o5` revising `i9j0k1l2m3n4`. The budget tables migration took `j0k1l2m3n4o5` first, so this migration is `k1l2m3n4o5p6` revising `j0k1l2m3n4o5`.
- **Divergence: migration downgrade.** The built downgrade drops each index before its table. The plan dropped only the tables.

## Open questions

- Should the scraper cover other CivicClerk boards, such as Zoning Board of Adjustment and City Council? The "first category containing planning" rule would also need to be stricter if a second planning category appears.
- Should rows for meetings or files that CivicClerk removes be deleted or flagged?
- Should scanned PDFs go through OCR?
