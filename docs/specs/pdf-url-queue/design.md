# PDF URL queue: design

**Status:** Done
**Created:** 2026-10-31
**Updated:** 2026-11-14

## Overview

The police log PDF queue lives in a Postgres `pdf_urls` table, not a MongoDB collection.
MongoDB stays for document-shaped work.
The spiders, items and requeue rules keep their shape; only the storage calls changed.

## Data flow

```
build_daily_urls ── UrlRecordItem ──> UrlRecordPipeline ──> INSERT ... ON CONFLICT DO NOTHING ──> pdf_urls
process_urls.start() ── requeue + claim (one transaction) ──> pdf_urls
process_urls.parse() ── PoliceLogPdfItem ──> PoliceLogPipeline ──> log_entries + pdf_urls (one transaction)
process_urls errors ── UPDATE pdf_urls SET state='error' ──> pdf_urls
```

- **Discovery:** `UrlRecordPipeline` buffers validated records and inserts them in one statement on `close_spider`.
  A URL already in the table is left alone.
- **Claim:** `process_urls` opens one transaction, runs two requeue statements, then claims `pending` rows with `FOR UPDATE SKIP LOCKED`, setting `in_progress`, `claimed_at` and `attempts + 1`.
  Concurrent runs never claim the same URL.
- **Requeue:** an `in_progress` row older than the 2 hour lease becomes a `download` error ("Claim expired").
  An `error` row with `error_kind = 'download'` and under 3 attempts goes back to `pending`.
  A `parse` or `save` error stays put until a parser fix and a reprocess, because its text is already archived.
- **Save:** `PoliceLogPipeline` saves a PDF's entries and marks its URL `complete` in one transaction.
  On any failure it rolls back, marks the URL `error` in a new transaction, and re-raises.
- **Timestamps:** the lease cutoff and `claimed_at` are naive UTC values from Python, like every other timestamp in the schema, not `now()`.

## Data model

`pdf_urls`: `id`, `canonical_url` (unique), `archive_url` (the Wayback Machine copy, used when the canonical URL stops serving a PDF), `log_date`, `state`, `attempts`, `claimed_at`, `completed_at`, `error_kind` (`download`, `parse` or `save`), `error_message`, `parsed_count`, `stored_count`, `skipped_count`, `header_lines`, `parser_version`, `content_hash`, `extractor_version`, `created_at`.
The PDF's own text is not stored here; it is archived in MongoDB.
`state` is checked against `pending`, `in_progress`, `complete`, `error`.
An index on `(state, created_at)` serves the claim query.

## Failure handling

- A crash after the claim leaves rows `in_progress`; the lease expiry returns them to the queue.
- A crash between the entry inserts and the commit loses both together, so the URL is retried and nothing is half saved.
- If marking a URL `error` itself fails, the lease expiry covers the row.

## Decisions

- **Postgres instead of MongoDB for the queue.**
  Postgres already ran a correct work queue for LLC lookups.
  The URL state change and the entry inserts share one transaction, so a PDF is complete exactly when its entries are saved.
  Rejected: keep MongoDB and order the writes carefully (entries first, then the URL).
  A crash between the two writes still needs the lease to recover, and every reader has to know two databases.
- **No data migration.**
  Rejected: copying the Mongo `urls` documents.
  The next `build_daily_urls` run rediscovers every PDF still linked from the index page, and `log_entries` drops reprocessed entries as duplicates on `case_number`.
- **Python timestamps instead of `now()`.**
  `now()` is converted to the session time zone; Python values keep both sides of the lease comparison the same.

## Testing

Tests compile the claim and requeue statements under the Postgres dialect, check that requeue runs before claim in one commit, and check that the pipeline commits entries and the URL update together and, on failure, commits only the `error` update.
