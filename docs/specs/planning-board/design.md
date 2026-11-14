# Planning board: design

**Status:** Done
**Created:** 2026-06-03
**Updated:** 2026-11-14

## Overview

A standalone Playwright script reads the public CivicClerk OData API from inside a real Chromium context, because the WAF returns 404 to plain HTTP clients.
It finds the Planning Board category, pages through its events with published files expanded, downloads each file, extracts PDF text with pypdf, and upserts meetings and documents into two Postgres tables.
A daily Airflow DAG (`civicclerk_planning`, 05:00 UTC) runs `scripts/scrape/scrape_civicclerk.py`.

## Data flow

```
load the portal home page (cookies, headers)
  -> GET /v1/EventCategories            -> pick the "planning" category
  -> GET /v1/Events?$filter=...         -> pages of 100 events with publishedFiles
  -> per event: upsert planning_meetings
       per file: download -> pypdf text -> upsert planning_documents
  -> one commit for the whole run
```

The script follows the pattern of `scripts/scrape/scrape_llcs.py`.
`run` stamps every row with one `scraped_at`.
Parsing (`parse_event`, `parse_file`, `extract_text_from_pdf`) is pure and unit tested; the network functions take the Playwright request context.

## Data model

- `planning_meetings`: keyed on `civicclerk_event_id`; title, category, meeting date, location, status, portal URL.
- `planning_documents`: keyed on `civicclerk_file_id`; the event id, file name, type (Agenda, Minutes, Attachment), download URL and extracted `raw_text`.
- Both upsert with `ON CONFLICT ... DO UPDATE`.
  Documents join to meetings by event id, with no foreign key.

## Failure handling

- A home page that does not load, a missing planning category, or a failed database write fails the run, and Airflow retries once.
- A bad date or status becomes null.
- A failed download, a non-PDF response or an unparsable PDF stores the document with null `raw_text`.
- All writes are one transaction, so one bad row discards the run.
- Known gaps: an API error response is parsed without a status check, and a PDF with no text layer stores newlines instead of null.

## Decisions

- **Playwright request context instead of httpx.**
  Loading the portal first gives the context the cookies the WAF wants.
- **Category found by name at runtime.**
  A hardcoded group id would break silently if CivicClerk renumbered categories.
- **Store extracted text, not files.**
  Text is what search needs.
  The download URL is kept so a file can be fetched again.
- **No foreign key from documents to meetings.**
  Both are keyed by CivicClerk ids and written in the same run.

## Open questions

- Cover other boards, such as Zoning Board of Adjustment and City Council?
- Delete or flag meetings and files that CivicClerk removes?
- Run scanned PDFs through OCR?
