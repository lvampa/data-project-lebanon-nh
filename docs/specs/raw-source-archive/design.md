# Raw source archive: design

**Status:** Draft
**Created:** 2026-11-06
**Updated:** 2026-11-07

## Overview

A Scrapy downloader middleware copies each archived response into a buffer, and a small archive class writes the buffer to MongoDB in batches (requirements 1 to 3).
The middleware returns the response untouched, so the spider callbacks and Postgres pipelines run exactly as before.
The police log reprocess job reads archived PDFs back by canonical URL or content hash, and a replay command does the same for parcel pages through the VGSI parser and pipeline (requirement 4).
The normalization job writes one `ai_calls` document per AI call through the same best-effort writer (requirement 6).
A daily `mongodump` backs the archive up, because it holds the only copy of the PDFs the police log parser reads (requirement 7).
Tests run against a `_test` MongoDB database through a pytest plugin, like the Postgres one (requirement 5).

The writing half ships between police log pipeline PR 1 and PR 2: it needs only `pdf_urls`, the process spider's `pdf_url` in `cb_kwargs`, and the `migrate` service.
The reads, extra sources, backup, and check command ship before police PR 2b, which drops the raw text columns: the gate before that pull request runs the check command and needs a restored backup.

## Architecture

```
            process spider ─┐                         ┌─► callbacks ─► pipelines ─► Postgres
                            ├─► download ─► response ─┤
            VGSI spider ────┘                         └─► RawArchiveMiddleware ─► buffer (50)
                                                                                     │ bulk upsert
                                                                                     ▼
                                                                         MongoDB raw_sources

  police reprocess ─► raw_sources ─► pypdf ─► ingest_pdf_url ─────────────────────► Postgres
  replay command ───► raw_sources ─► HtmlResponse ─► parse_parcel ─► PropertyPipeline ─► Postgres

  normalize job ────► AiCallLog ─► MongoDB ai_calls          Postgres keeps ai_call_id
  backup DAG ───────► mongodump ─► backup folder, 7 days kept
```

MongoDB holds originals and records; it is never the source of truth for a curated value.
For police log PDFs it is the only copy of the parser's input, which is why requirement 7 exists.

## Components and interfaces

### Archive class

`shared/mongo/src/mongo/archive.py`.

```python
class RawArchive:
    def __init__(self, collection: Collection, batch_size: int = 50) -> None   # 1 for police log PDFs
    def add(self, source: str, source_key: str, response: ArchivedResponse) -> bool | None
    def flush(self) -> ArchiveCounts          # stored, seen_again, failed
    def keys(self, source: str) -> list[str]
    def versions(self, source: str, source_key: str) -> list[dict]          # newest first
    def newest(self, source: str, source_key: str) -> dict | None
    def by_hash(self, source: str, source_key: str, content_hash: str) -> dict | None

def stored_body(version: dict) -> bytes | None                              # None when truncated
```

- The reads are for operator commands and reprocess, not the crawl, so a MongoDB error is raised to the caller instead of counted.
- `ArchivedResponse.text`, when set, is stored compressed as `text_gzip` beside the body; the budget downloader uses it.

- `add` hashes and compresses the body, appends one `UpdateOne` to the buffer, and flushes when the buffer reaches the batch size (3.3).
  The batch size is per spider: 1 for the process spider, so each PDF is written before its callback runs, and 50 for the VGSI spider.
  At 100 PDFs a run that is 100 small writes, well inside the overhead limit (3.6).
- Each `UpdateOne` is an upsert keyed on source, source key, and content hash.
  `$setOnInsert` writes the body and first-fetch details; `$set` moves `last_seen_at`; `$inc` adds to `seen_count`.
  So one write both stores a new version and records a repeat (2.1, 2.2).
- `flush` sends one unordered `bulk_write` and counts upserted as stored and matched as seen again.
- Any `PyMongoError` is caught, counted as failed, and logged; nothing is raised (3.1).
- The client is built with `serverSelectionTimeoutMS=2000`, `connectTimeoutMS=2000`, and `socketTimeoutMS=5000`.
  The first two bound finding and reaching a server; the third bounds each operation's wait for a reply, so a server that accepts the connection and then hangs cannot stop the crawl.
  pymongo's `timeoutMS`, or a `pymongo.timeout()` block, is not used: measured on this stack, it overrides the 2 second selection limit, and an unreachable server then took 5 seconds.
  After any of these timeouts the archive marks itself down and drops later writes for the run, counting them as failed (3.2).
- Writes are synchronous on Scrapy's reactor thread, like the Postgres pipelines.
  The crawl is throttled to one request per domain, so two flushes per 100 PDFs cost a few milliseconds; a thread would add buffer locking for no measurable gain.
- `content_hash(source, body)` in `shared/mongo` removes the page-state fields of a parcel page before hashing (2.3).
  It is the only hash function: the archive and the process spider both call it, so `pdf_urls.content_hash` always finds its version with `by_hash`.

### Middleware

`scrapers/middlewares/raw_archive.py`, enabled in `DOWNLOADER_MIDDLEWARES` at priority 50.
Scrapy calls `process_response` from the highest number to the lowest, so at 50 it runs after `HttpCompressionMiddleware` (590) and `RedirectMiddleware` (600) and sees the same decompressed, final body as the callback (1.8).

- A spider opts in with two attributes: `archive_source`, and `archive_key(response) -> str | None`.
  The process spider returns the canonical URL from the request's `pdf_url`, so a PDF fetched from its Wayback copy is still keyed by the city URL.
  It returns `None` when the body does not start with `%PDF`, because the city sometimes answers 200 with an HTML page, which is why the spider falls back to the Wayback copy.
  The VGSI spider returns the parcel ID for `Parcel.aspx` pages and `None` for street pages (1.7).
- `process_response(request, response)` takes no `spider` argument, which Scrapy 2.16 warns about here as it does for pipelines; the spider comes from the crawler.
- It adds the response when the spider opted in, the status is 200, the key is not `None`, and the response's `flags` do not contain `cached`, then returns the response unchanged (1.7).
- For the process spider the write happens right there, and the middleware sets `response.meta["archived"]` to whether it succeeded (3.8).
  `add` returns whether the write it triggered worked, or `None` while the version is still buffered, so the flag is set only when a write happened; a parcel page mid-batch, or a response that is not an original, gets none.
  The spider sets `archive_batch_size = 1`; the middleware reads it from the spider class, and the default is 50.
  The police pipeline reads that flag: a parse or save error on a PDF that was not archived becomes kind `download`, so it is downloaded again.
- On `spider_closed` it flushes and logs the counts (3.4).
- `RAW_ARCHIVE_ENABLED` in Scrapy settings, default true, and a per-spider `custom_settings` override turn it off (3.7).
- A downloader middleware sees the raw body before any callback, so the Postgres path does not carry bodies around.

### Scripts that are not Scrapy spiders

The LLC lookup and the budget downloader live in `scripts/` and do not run through Scrapy, so they call `RawArchive` directly after each download (1.9, 1.10).

- `scripts/scrape/scrape_llcs.py` adds `page.content()` after the business page loads, as source `nh_sos_business`, keyed by the business ID from the URL, or by the searched name when there is none.
  It keeps parsing the same HTML into the curated LLC tables, which do not change.
- `scripts/scrape/download_budget_pdfs.py` adds the PDF bytes and the text it extracts, as source `budget_pdf`, keyed by the source URL.
  It keeps writing the local text files the budget import reads.
- Both flush at the end of the run and follow requirement 3: an archive failure is logged and counted, and the script's own work goes on.

### Police log texts

Two text sources sit beside `police_log_pdf`, and both follow the archive's one rule: a version is one distinct body for one source key, hashed with `content_hash`.

- `police_log_entry_text`: key = case number, body = JSON with `raw_text`, `raw_reason_action`, `source_url`, and `parser_version` (8.2).
  After the police log pipeline commits a PDF's entries, it writes one version per entry, best-effort.
  Reprocess writes them again; at the same parser version an unchanged text only moves the seen count, and a changed one becomes a new version.
  Because `parser_version` is in the body, a parser bump stores a new version for every entry even when its text is the same, so the history shows which parser cut what.
- `police_log_text`: key = canonical URL, body = a log PDF's extracted text.
  Only the legacy import writes it, for PDFs whose text was stored before the archive existed.

Police log reprocess takes the newest `police_log_pdf` body for a URL and extracts it with pypdf; if there is none, it takes the newest `police_log_text` (4.1).

### Legacy import

`python -m maintenance.archive_raw_text` from `scrapers/`, built in police log pipeline PR 2b, run once before the migration that drops the raw text columns (8.4 to 8.8).
The sources and the lookup it uses live in `shared/mongo/src/mongo/raw_text.py`, which the migration imports too, so both agree on where each value goes:

1. For each non-null `pdf_urls.raw_text`, and each Mongo `urls` document with stored PDF text, write a `police_log_text` version keyed by canonical URL.
   When both hold different text for one URL, each becomes its own version.
2. For each `log_entries` row, write a `police_log_entry_text` version keyed by case number, with `raw_text`, `raw_reason_action`, `source_url`, and the row's parser version.
3. Leave the `urls` collection and every Postgres row exactly as they are.
4. Report copied against existing for `log_entries` rows and `pdf_urls` texts, and exit non-zero if either falls short.

Every write is the archive's usual upsert on source, key, and content hash, so a second run matches and changes nothing (8.8).

The migration's `upgrade` first compares every key in the raw text columns with the archive, and stops before dropping anything if one is missing, naming the command to run (8.12).
So the drop cannot run ahead of the copy on any database, including the live one.
When no raw text remains to drop, as in CI or a new database, the guard does not connect to MongoDB at all.

### Replay and check commands

`scrapers/maintenance/raw_sources.py`.

```
raw_sources replay --source vgsi_parcel [--parcel PID ...]
raw_sources check
raw_sources versions --source SOURCE --key KEY
raw_sources restore-check BACKUP
```

- Police log PDFs are not replayed here: the police log pipeline's reprocess job reads them with `RawArchive.newest(source, key)` and `RawArchive.by_hash(source, key, content_hash)` (4.1).
- Parcel replay: build a Scrapy `HtmlResponse` from the newest version's body and URL, call `VgsiPropertySpider.parse_parcel`, and pass each item through `PropertyPipeline` (4.2).
- Replay reads the archive and never writes it (4.3), and logs the counts in 4.4.
- `check` reports size and versions per source, counts log PDFs with an archived body and text-only ones, lists the text-only ones by URL, lists log PDFs with neither, parcels with none, and `ai` normalizations with a null `ai_call_id` (2.5, 4.5).
  A truncated PDF version counts as no body.
  It exits non-zero while any `complete` or `error` log PDF has neither, so the gate before police PR 2b can run it.
  The `ai_call_id` line lands with police log PR 4, which adds the normalization tables.
- `versions` lists one key's versions (4.6).
- `restore-check` restores a backup into `scraped_data_restore_test` and compares document counts with the live archive (7.5).
  The live database only grows, so it fails when a live collection is empty in the restore, or the restore holds more than live.
  It drops the restore database afterwards, and runs in the Airflow image, which has `mongorestore`.

### AI call log

`AiCallLog` in `shared/mongo/src/mongo/ai_calls.py` writes one document per call with the same timeouts and mark-down behavior as `RawArchive` (6.5).
`record(call) -> str | None` returns the new document's ID, or `None` when the write failed, so the normalization job stores `ai_call_id` only when there is one.
The job counts the `None`s and logs them as lost call records (police log 8.14).
The ID is never generated client-side, so Postgres never points at a record that does not exist.
Calls are written one at a time; a run makes at most 10.

### Backup

A `mongo_backup` Airflow DAG runs daily: `mongodump --gzip --archive` of the archive's database into `/opt/backups/mongo` inside the container (7.1, 7.2).
That path is a bind mount of the host folder, so the backup is outside the `mongo_data` volume.
`compose.yml` mounts it on the Airflow services as `${MONGO_BACKUP_DIR:-${HOME}/backups/data-project/mongo}:/opt/backups/mongo`, so the host folder is `~/backups/data-project/mongo` unless `.env` sets `MONGO_BACKUP_DIR`.
The default uses `${HOME}` so the path is absolute whether or not the shell or Compose expands `~`.
`mongodump` is part of MongoDB Database Tools, which the Airflow image does not have, so `docker/Dockerfile.airflow` installs the `mongodb-database-tools` package.
Running it inside Airflow, rather than as a separate compose service from the `mongo:8` image, means a failed backup shows as a failed DAG run (7.4).
It deletes backups older than the 7 newest (7.3) and fails the task on a non-zero exit (7.4).
The DAG has one task, `python maintenance/mongo_backup.py`, like the other DAGs; its first step checks the folder exists and is writable, and fails with a message that names it, before `mongodump` starts.
`mongodump` and `mongorestore` get the password through a `--config` file, not the command line, so it stays out of the process list and the task log.
The host folder is created by hand before the first run, because when Docker creates a missing bind-mount folder it is owned by root, and the Airflow user (uid 50000) cannot write to it.
Docker Desktop on a Mac usually hides this, but CI and any Linux host do not.
Unless it points at another disk, the bind mount is on the same disk as the `mongo_data` volume, so it protects against a lost volume but not a failed disk.

### Startup

`init_indexes` creates the archive indexes.
The `migrate` service runs it after `alembic upgrade head`, so a fresh stack has them before any spider runs.
The `mongo` service gets a healthcheck, `mongosh --eval "db.adminCommand('ping')"`, so the `migrate` service and CI's `docker compose up --wait` wait until it accepts connections.

## Data models

One document per version in `raw_sources`:

```json
{
  "_id": "ObjectId",
  "source": "vgsi_parcel",
  "source_key": "1000",
  "url": "https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=1000",
  "status": 200,
  "content_type": "text/html; charset=utf-8",
  "content_hash": "sha256 hex",
  "size_bytes": 83278,
  "body_gzip": "BinData",
  "truncated": false,
  "first_fetched_at": "ISODate",
  "last_seen_at": "ISODate",
  "seen_count": 1,
  "spider": "vgsi_property"
}
```

Source-specific fields on the same document:

| Source | Extra fields |
|---|---|
| `police_log_pdf` | None. |
| `police_log_text` | None; the body is the extracted text. |
| `police_log_entry_text` | None; the body is JSON with `raw_text`, `raw_reason_action`, `source_url`, and `parser_version`. |
| `budget_pdf` | `text_gzip`: the extracted text, because it came from a separate extraction step. |
| `vgsi_parcel`, `nh_sos_business` | None. |

Indexes:

| Index | Why |
|---|---|
| `{source, source_key, content_hash}`, unique | The upsert key; one document per distinct body. |
| `{source, source_key, first_fetched_at: -1}` | Newest version first, for replay and `versions`. |
| `{source, last_seen_at}` | The check command's per-source counts. |

One document per AI call in `ai_calls`:

```json
{
  "_id": "ObjectId",
  "field": "incident_type",
  "raw_values": ["MV Complaint", "BUSINESS CHECK - OPEN"],
  "prompt": "text",
  "raw_answer": "text, as the backend returned it",
  "accepted": [{"raw": "MV Complaint", "category": "Traffic", "normalized_type": "Motor vehicle complaint", "unsure": false}],
  "ai_backend": "claude_cli",
  "model": "the configured model",
  "prompt_version": "incident_type-1",
  "duration_ms": 8400,
  "outcome": "ok | partial | failed | unavailable",
  "error": null,
  "called_at": "ISODate"
}
```

| Index | Why |
|---|---|
| `{field, prompt_version, called_at: -1}` | Listing calls by prompt version, for the evaluation work (6.4). |
| `{accepted.raw}` | Finding the AI's answer for one raw value when Connor corrects it. |

Postgres links to it through `ai_call_id` on each normalization row (6.3).

Expected size, from one fetch of each:

- A log PDF is about 100 KB, so the 663 known PDFs are about 70 MB, and each new day adds one.
- A parcel page is 83 KB of HTML and 19 KB compressed.
  At an estimated 5,000 parcels, one full set is about 95 MB, and later scrapes add only parcels that changed.
- AI call records are a few kilobytes each, at most 10 a day after the backlog.
- Entry texts add about 40 KB per PDF, the size of its extracted text, before compression.
- Business pages and budget PDFs number in the hundreds, not thousands.
- That is well under 1 GB a year, which is why there is no pruning yet, and why 7 daily backups fit on any disk.

## Error handling

| Failure | What happens | Criteria |
|---|---|---|
| MongoDB down at start | First batch times out after 2 seconds; archive marks itself down; Postgres path unaffected. | 3.1, 3.2 |
| One batch write fails | Logged and counted; later batches still try. | 3.1, 3.4 |
| MongoDB accepts the connection, then hangs | The 5 second operation timeout fires; archive marks itself down. | 3.1, 3.2 |
| Duplicate upsert race between two runs | The unique index turns it into a matched write; counted as seen again. | 2.1 |
| The spider crashes with a partly full buffer | Up to 49 bodies whose Postgres rows already committed are lost; the check command lists them, and the police reprocess sends them back to download. | 3.3, 4.5 |
| Body over 15 MB compressed | Stored without body, `truncated: true`, warning. | 1.6 |
| Replay finds a truncated version | Skipped and counted as no usable body. | 4.4 |
| Replay finds no version | Counted as no usable body. | 4.4 |
| An AI call record cannot be written | `record` returns `None`; the normalization is stored without `ai_call_id`. | 6.5 |
| Backup fails | The DAG task fails and shows red; the previous backups stay. | 7.4 |

## Testing strategy

- A pytest plugin in `shared/mongo`, loaded through a `pytest11` entry point like the Postgres one, because `mongo` builds its client from `MONGO_DB` at import.
  It sets `MONGO_DB=scraped_data_test`, stops the run if the name does not end in `_test`, and drops the archive collection after each test (5.1 to 5.3).
- CI starts `mongo` next to `postgres` with `docker compose up -d --wait`.
- Archive class: new version, repeat, changed body, page-state fields ignored, oversized body, a failed batch, the selection timeout, and a hung server (a socket that accepts and never answers) that marks the archive down.
- Police write flag: an archive write that fails, then a parse error, leaves the URL record kind `download`.
- Middleware: a fake crawl through Scrapy's test responses for both spiders, a street page not archived, a non-200 not archived, a cached response not archived, a gzip-encoded response archived decompressed, and the setting that turns it off.
- MongoDB unreachable: point the archive at a closed port and run the process pipeline against the Postgres test harness; entries are stored (5.4).
  The exit-code half of 3.5 needs the process runner, so that test lands with police log pipeline PR 2.
- Reads: `newest` and `by_hash` return the right version when a key has two.
- Parcel replay: archive one saved parcel page, replay it, and compare with a normal ingest.
- AI call log: a record is written and its ID returned; an unreachable Mongo returns `None` without raising.
- Entry texts: one `police_log_entry_text` version per entry after commit; reprocess at the same parser version with unchanged text only moves the seen count.
- Legacy import: copies seeded `log_entries` rows to `police_log_entry_text` and `pdf_urls` and `urls` texts to `police_log_text`; leaves `urls` and Postgres unchanged; exits non-zero when a row or text is missing; and a second run changes nothing.
- Reprocess fallback: a URL with only a `police_log_text` version is reparsed from that text.
- LLC and budget scripts: each archives its download, and an unreachable Mongo leaves their own output unchanged.
- Backup: the DAG's structure test, and a QA run that backs up, prunes, and restores into a test database.
- Overhead (3.6): a QA run of the process job on 100 PDFs with the archive on and off; not in the test suite.

## Decisions

### A document store for the raw layer, not Postgres JSONB

Postgres can hold the same thing in a `raw_sources` table with a `bytea` body and a `jsonb` metadata column, and that has one real advantage: a raw copy could commit in the same transaction as its curated rows.

The archive goes in MongoDB anyway:

- The raw layer is write-once, append-mostly, and shaped differently per source: PDF bytes, parcel HTML, and later agenda files with their own metadata.
  A document per version holds each shape with no migration when a source adds a field.
- It keeps large, rarely read blobs out of the operational database: out of its backups, its Alembic migrations, the dbt models' neighborhood, and the test harness's rolled-back transactions.
- It separates failure: the archive can be down, full, or slow without touching a Postgres transaction, which is what requirement 3 asks for.
  The same-transaction advantage of JSONB is the opposite of that goal.
- Connor's rule for the project: every parsed, structured field goes in Postgres, and raw, unparsed source goes here, where nothing scraped is thrown away.
  That moved the police log PDF text, each entry's raw text, and the AI call records out of Postgres, so Postgres keeps a content hash or an ID as the reference, and it brought the LLC pages and budget PDFs into the archive.
- Upsert on a unique compound key gives store-once with a seen count in one write.
- It is also the document-database practice Connor wants, and the split is a clear story: originals in a document store, curated relational data in Postgres.

Rejected: Postgres JSONB and `bytea`, for the reasons above.
Rejected: files on disk or S3. No query on metadata, and one more thing to back up and serve.
Rejected: GridFS. Every body is far under MongoDB's 16 MB document limit.

### Middleware, not an item pipeline

- Rejected: an archive item pipeline.
  Pipelines see items, not responses, so every item would have to carry the raw body through the Postgres path.
- Rejected: archiving inside each spider callback.
  It mixes storage into parsing code and has to be repeated per spider.

### Store distinct bodies, not every fetch

- Rejected: one document per fetch.
  Weekly parcel scrapes would store thousands of identical copies; the seen count and last-seen time keep the same information.

### The archive is the only copy of police log PDF text

Connor chose to drop the extracted text from Postgres, so the police log reprocess job reads the archive.

- Rejected: keeping the text in `pdf_urls` as well, which the reviewer and the PM recommended.
  It kept reprocessing Postgres-only and left the archive a pure side copy.
- What the choice costs, and how the design pays for it:
  the archive's writing ships earlier, before Postgres stops storing the text;
  it is backed up daily, and police PR 2 waits on a gate in tasks.md: a restored backup, the legacy import, and every `complete` URL record archived;
  reprocess depends on pypdf, so the extractor version is recorded and a pypdf bump counts as a parser change;
  police PDFs are written one at a time, so the process job knows whether each was archived, and a PDF the archive missed goes back to the download queue instead of getting stuck.

### Compress in the application

- Rejected: relying on MongoDB's storage compression alone.
  Gzip in the document also shrinks what crosses the network and what a replay reads, and keeps the stored body exactly recoverable.

## Open questions

1. **Archive the URL discovery pages?**
   The city's Daily Police Log index page shows what was listed on a day.
   It is small and would make the audit trail complete, but nothing reads it yet.
2. **Parcel count.**
   The 5,000 figure is an estimate; the first full VGSI run will give the real number for the size estimate.
3. **Postgres backups.**
   A separate decision, outside this spec.

Decided: the backup folder is `~/backups/data-project/mongo` on the host, Connor's choice.
It is on the same disk as the Docker volume, so it survives a lost volume but not a disk failure; pointing `MONGO_BACKUP_DIR` at an external drive or a synced folder would survive both.

Answered: the same log PDF downloaded twice was byte-identical (87 KB, same SHA-256), so re-downloads do not make new versions.
