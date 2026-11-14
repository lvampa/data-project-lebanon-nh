# Raw source archive: design

**Status:** In progress
**Created:** 2026-11-06
**Updated:** 2026-11-14

## Overview

Every scraped original is kept in MongoDB, so a parser fix can be replayed against what the city actually published.
A Scrapy downloader middleware copies each archived response into a buffer, and a small archive class writes the buffer to a `raw_sources` collection in batches.
The middleware returns the response untouched, so spider callbacks and the Postgres pipelines run as before.
Archiving is best effort: if MongoDB is down, the crawl and the Postgres writes carry on.

The archive holds the only copy of the police log PDFs, which is why the reprocess job reads it and why a hand-run backup exists.

## Data flow

```
process spider ─┐                         ┌─► callbacks ─► pipelines ─► Postgres
                ├─► download ─► response ─┤
VGSI spider ────┘                         └─► RawArchiveMiddleware ─► buffer ─► bulk upsert ─► MongoDB raw_sources

police reprocess ─► raw_sources ─► pypdf ─► ingest_pdf_url ─► Postgres
replay command ───► raw_sources ─► HtmlResponse ─► parse_parcel ─► PropertyPipeline ─► Postgres
normalize job ────► AiCallLog ─► MongoDB ai_calls          (Postgres keeps ai_call_id)
backup script ────► mongodump ─► one dated file per run
```

MongoDB holds originals and records.
It is never the source of truth for a curated value.

## How it works

- **A version is one distinct body** for one source and key, identified by a SHA-256 of the body.
  One upsert on `(source, source_key, content_hash)` stores a new version or records a repeat with a seen count and a last-seen time.
  Page-state fields of parcel pages are removed before hashing, so an unchanged page is not a new version.
- **Sources:** `police_log_pdf` (keyed by canonical URL), `vgsi_parcel` (parcel ID), `nh_sos_business`, `budget_pdf`, and two police log text sources, `police_log_text` and `police_log_entry_text`.
- **Middleware** (`scrapers/middlewares/raw_archive.py`, priority 50) sees the same decompressed, final body as the callback.
  A spider opts in with `archive_source` and `archive_key(response)`.
  The process spider returns `None` for a body that is not a PDF, because the city sometimes answers 200 with an HTML page.
- **Batching:** the VGSI spider flushes every 50 responses.
  The process spider flushes after each PDF and tells the pipeline whether the write worked, so a PDF the archive missed goes back to the download queue instead of getting stuck.
- **Timeouts:** 2 seconds to find or reach a server and 5 seconds per operation.
  After a timeout the archive marks itself down, drops later writes for the run, and counts them as failed.
- **Scripts outside Scrapy** (LLC lookup, budget downloader) call `RawArchive` directly after each download.
- **Reads** go through `RawArchive.newest`, `by_hash` and `versions`, and raise on a MongoDB error, because they serve operator commands, not the crawl.
- **Commands** in `scrapers/maintenance/raw_sources.py`: `replay` (parcel pages through the parser, read-only), `check` (sizes, log PDFs with no usable body, AI normalizations with no call record), `versions`, and `restore-check`.
- **AI call log:** `AiCallLog` writes one `ai_calls` document per AI call and returns its ID, or `None` on failure, so Postgres never points at a record that does not exist.
- **Backup:** `python maintenance/mongo_backup.py`, run by hand in the Airflow container, writes a dated `mongodump` file to a bind-mounted host folder.
  It never overwrites a backup and deletes its own partial file on failure.
  The folder is on the same disk as the Mongo volume by default, so it protects against a lost volume but not a failed disk.
- **Startup:** `uv run migrate` creates the archive indexes after the Alembic upgrade.

## Data model

One document per version in `raw_sources`: `source`, `source_key`, `url`, `status`, `content_type`, `content_hash`, `size_bytes`, `body_gzip`, `truncated`, `first_fetched_at`, `last_seen_at`, `seen_count`, `spider`.
A body over 15 MB compressed is stored without its body and marked `truncated`.
A unique index on `(source, source_key, content_hash)` is the upsert key.
Two more indexes serve newest-first reads and per-source counts.

One document per AI call in `ai_calls`: the field, the raw values, the prompt, the raw answer, the accepted items, the backend and model, the prompt version, duration, outcome and error.

Size is small: the police log PDFs are about 100 KB each, parcel pages about 19 KB compressed, and the total stays well under 1 GB a year, so there is no pruning.

## Failure handling

- MongoDB down at start: the first batch times out, the archive marks itself down, and the Postgres path is unaffected.
- A crash with a partly full buffer loses up to 49 parcel bodies whose Postgres rows are saved; the check command lists them.
- A truncated or missing version is skipped by replay and counted as having no usable body.

## Testing

A pytest plugin in `shared/mongo` points tests at `scraped_data_test`, refuses any database name that does not end in `_test`, and drops the archive collection after each test.
Tests cover the archive class (new version, repeat, changed body, oversized body, failed batch, timeouts, a hung server), the middleware for both spiders, an unreachable MongoDB with the Postgres path still working, reads, replay, the AI call log, and backup cleanup.

## Decisions

- **A document store for the raw layer, not Postgres JSONB.**
  The raw layer is write-once and shaped differently per source.
  A document per version needs no migration when a source adds a field, keeps large blobs out of the operational database and its backups, and lets the archive fail without touching a Postgres transaction.
  Rejected: Postgres `bytea` and JSONB, whose one advantage (a raw copy in the same transaction) is the opposite of the failure isolation wanted here.
  Rejected: files on disk or S3, which have no metadata queries.
  Rejected: GridFS, since every body is far under MongoDB's 16 MB limit.
- **The rule for the two databases:** parsed, structured fields go in Postgres, and raw, unparsed source goes in MongoDB, where nothing scraped is thrown away.
  Postgres keeps a content hash or an ID as the reference.
- **Middleware, not an item pipeline.**
  Pipelines see items, not responses, so every item would carry its raw body through the Postgres path.
  Rejected: archiving inside each callback, which mixes storage into parsing code.
- **Store distinct bodies, not every fetch.**
  Rejected: one document per fetch, which would store thousands of identical parcel pages.
- **The archive is the only copy of police log PDF text.**
  Rejected: keeping the text in `pdf_urls` as well, which would keep reprocessing Postgres-only.
  The cost is paid by hand-run backups, by recording the extractor version (a pypdf bump counts as a parser change), and by writing PDFs one at a time.
- **Gzip in the application.**
  Rejected: relying on MongoDB storage compression alone, which does not shrink what crosses the network or what a replay reads.

## Open questions

- Archive the city's URL discovery pages, so the audit trail shows what was listed each day?
- The 5,000 parcel count is an estimate; the first full VGSI run will give the real number.
