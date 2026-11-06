# PDF URL queue: design

**Status:** Done
**Created:** 2026-10-31
**Updated:** 2026-11-06

## Overview

Move the police log PDF queue from the MongoDB `urls` collection to a Postgres `pdf_urls` table.
MongoDB stays in the stack for document-shaped work.
The spiders, items and requeue rules keep their shape; only the storage calls change.
Covers requirements 1 to 5.

## Architecture

```
build_daily_urls ── UrlRecordItem ──> UrlRecordPipeline ──> INSERT ... ON CONFLICT DO NOTHING ──> pdf_urls
process_urls.start() ── requeue + claim (one transaction) ──> pdf_urls
process_urls.parse() ── PoliceLogPdfItem ──> PoliceLogPipeline ──> log_entries + pdf_urls (one transaction)
process_urls errors ── UPDATE pdf_urls SET state='error' ──> pdf_urls
```

## Components and interfaces

### `UrlRecordPipeline`

Validates each `UrlRecordItem` with `UrlRecord` and buffers it.
On `close_spider`, if the buffer is not empty, it runs one multi-row insert inside a `logfire.span`:

```sql
INSERT INTO pdf_urls (canonical_url, archive_url, log_date, state, created_at)
VALUES ...
ON CONFLICT (canonical_url) DO NOTHING
```

This matches the old `$setOnInsert` upsert: new URLs are added, existing rows are not touched.

### `ProcessUrlsSpider.start()`

Opens one session, runs the two requeue statements, then the claim, and commits.
The requeue rules are carried over from the Mongo version unchanged:

```sql
-- 1. Expire stale claims (CLAIM_LEASE = 2 hours).
UPDATE pdf_urls SET state = 'error', error_message = 'Claim expired'
WHERE state = 'in_progress' AND claimed_at < :lease_cutoff;

-- 2. Retry errors under the attempt limit (MAX_ATTEMPTS = 3).
UPDATE pdf_urls SET state = 'pending'
WHERE state = 'error' AND attempts < :max_attempts;

-- 3. Claim.
UPDATE pdf_urls
SET state = 'in_progress', claimed_at = :now, attempts = attempts + 1
WHERE id IN (
  SELECT id FROM pdf_urls
  WHERE state = 'pending'
  ORDER BY created_at
  LIMIT :n
  FOR UPDATE SKIP LOCKED
)
RETURNING id, canonical_url, archive_url;
```

`:now` and `:lease_cutoff` are naive UTC values from Python, like every other timestamp column in the schema, rather than `now()`, which returns the session's time zone.
Each returned row is validated into a `PdfUrlClaim` model and passed to the request callbacks and errback.

### Error marking in the spider

The errback, the not-a-PDF paths, unreadable PDFs and zero-entry PDFs each run one `UPDATE pdf_urls ... WHERE id = :id` in a short session and commit.

### `PoliceLogPipeline`

For each `PoliceLogPdfItem`:

1. Validate every entry with `PoliceLogRecord`.
2. Inside a `logfire.span`, insert each entry with `ON CONFLICT (case_number) DO NOTHING`, then `UPDATE pdf_urls SET state = 'complete', raw_text, entry_count, completed_at WHERE id = :url_id`.
3. Commit once.

On any exception it rolls back, sets the URL to `error` in a new transaction, commits, and re-raises.

## Data models

```python
class PdfUrl(Base):
    __tablename__ = "pdf_urls"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    archive_url: Mapped[str | None] = mapped_column(Text)
    log_date: Mapped[date | None] = mapped_column(Date)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    entry_count: Mapped[int | None] = mapped_column(Integer)
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- `ck_pdf_urls_state`: `state IN ('pending', 'in_progress', 'complete', 'error')`.
- `idx_pdf_urls_state_created_at` on `(state, created_at)` serves the claim subquery.
- `archive_url` is the Wayback Machine copy used when the canonical URL no longer serves a PDF.

One Alembic migration creates the table, revising `22fc0163d5ff`; its downgrade drops the index and the table.

The scrapers models change with it:

- `UrlRecord.log_date` becomes a `date`, since the column is a `date`.
- `UrlDocument`, which wrapped a Mongo document with an `ObjectId`, is replaced by `PdfUrlClaim` (`id`, `canonical_url`, `archive_url`).
- `PoliceLogPdfItem.url_id` holds the integer `pdf_urls.id`.

## Error handling

- A crash after the claim commits leaves rows `in_progress`; requeue rule 1 expires them on a run after the lease.
- A crash between the entry inserts and the commit loses both together, and the URL is expired and retried.
  This is the ordering problem that two databases could not solve.
- If marking a URL `error` itself fails, the exception propagates and the lease expiry covers the row.

## Testing strategy

No database is available in the sandbox, so tests stay at the statement level.

- The claim statement compiles under the Postgres dialect with `FOR UPDATE SKIP LOCKED`, `ORDER BY created_at`, `LIMIT` and `RETURNING`.
- The requeue statements compile to the expected `WHERE` clauses and bound values (lease cutoff, attempt limit).
- `start()` runs requeue before claim in one commit, and yields one request per claimed row.
- `PoliceLogPipeline`, with `FakeSession`, commits the entry inserts and the `pdf_urls` update in one transaction, and on failure commits only the `error` update.
- `UrlRecordPipeline` compiles to an insert with `ON CONFLICT (canonical_url) DO NOTHING`, and skips the session when empty.
- `test_migrations.py` gains a case that `pdf_urls` rejects an unknown state; it runs only with `TEST_DATABASE_URL`.

## Decisions

### Postgres instead of MongoDB for the queue

Chosen because:

- Postgres already runs a correct work queue in `scripts/scrape/scrape_llcs.py` with `FOR UPDATE SKIP LOCKED`, so the pattern is proven here.
- The URL state change and the entry inserts share one transaction, so a PDF is complete exactly when its entries are saved.
- Readers of the queue's state and of the entries it produces use one database.

Rejected: keep MongoDB and order the writes carefully, as wave one did by committing entries first and marking the URL second.
It works, but a crash between the two writes still needs the lease to recover, and every reader has to know two databases.

### No data migration

Rejected: a script that copies the Mongo `urls` documents into `pdf_urls`.
The next `build_daily_urls` run rediscovers every PDF still linked from the index page.
Already-processed PDFs are processed again, and `log_entries` drops their entries as duplicates on `case_number`.
PDFs no longer linked anywhere are not rediscovered, but their entries are already in `log_entries`.

### Python timestamps instead of `now()`

The schema stores naive UTC everywhere.
`now()` would be converted to the session time zone, and the lease comparison uses a Python cutoff, so both sides use Python values.
