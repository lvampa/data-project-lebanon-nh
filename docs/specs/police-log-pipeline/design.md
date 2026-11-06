# Police log pipeline: design

**Status:** Draft
**Created:** 2026-11-06
**Updated:** 2026-11-06

## Overview

This design is written as changes on top of the `fix/integration` and `fix/url-queue` branches, which ship first.
It covers all fifteen requirements.

What those branches already give us:

| Already there | Where | Criteria it meets |
|---|---|---|
| URL queue in Postgres `pdf_urls`, unique on `canonical_url` | `fix/url-queue` | 2.1 |
| One `PoliceLogPdfItem` per PDF; entries and `complete` in one commit | `fix/url-queue` | 2.2, 2.3 |
| A commit per item, so one PDF's failure does not lose another | `fix/integration` | 2.6 |
| Claim with `claimed_at` and `attempts`, a 2 hour lease, a 3 attempt limit, an errback | `fix/url-queue` | most of 2.7, 2.9, 2.10 |
| Address PATCH keeps coordinates when geocoding fails | `fix/integration` | 6.12 |
| Category model and upsert in `scripts/models/incident_category.py` | `fix/integration` | part of 7.7 |
| Thin routers over `api/services/*`, paged lists, `require_admin` on writes | `fix/integration` | base for 7.3 to 7.5 |
| DAGs built from `dags/specs.py`, one run at a time, timeouts, `scripts/` in the image | `fix/integration` | 12.4, part of 12.5 |
| Migration up and down test on a real database | `fix/integration` | part of 13.4 |

What this design adds, in one paragraph:
One ingest function parses and upserts a PDF's entries, used by both the process job and a new reprocess script.
Raw values stay on `log_entries` and are never rewritten.
Normalized values live in the two existing lookup tables, each row carrying who produced it.
A normalization job fills them through an AI backend interface and checks every answer in code; a separate job geocodes locations.
Connor's edits go through the admin API, are marked `human`, and no job overwrites them.
dbt builds the consumer models, runs the data checks, and gives the admin API, the search sync, and the public export one definition of an incident.
The public export stays a manual step.
An evaluation command scores each backend, model, and prompt version against a labeled set.

## Architecture

```
city page ──► discover spider ──► pdf_urls (pending)
                                      │ claim (claimed_at, attempts)
                                      ▼
                    process spider: download, extract text
                                      │ one PoliceLogPdfItem per PDF
                                      ▼
            pipeline ──► ingest_log_text() ──► log_entries (raw values)
                              ▲                        │
     reprocess script ────────┘                        │ distinct raw values
     (stored text, no download)                        ▼
                                    normalize job ──► AI backend (claude -p, or Ollama)
                                           │           └─► ai_answers (append-only log)
                                           ▼
                 incident_type_categories, address_normalizations ◄── admin API (source = human)
                                           ▲
                                    geocode job ──► Nominatim (bounds, 1 per second)
                                           │
                                           ▼
                        dbt: staging ──► incidents ──► public 90 day models, with tests
                              ┌────────────┼────────────────┐
                        incidents API   search sync    report-gen (public export)

      evaluation command ──► AI backend ──► score report   (no database writes)
```

## Components and interfaces

### URL queue

The queue is the `pdf_urls` table from `fix/url-queue`.
The claim, lease, and retry statements in the process spider stay.
Changes:

- A new column, `error_kind`: `download`, `parse`, or `save`.
  An expired claim is kind `download`.
- `retry_failed_urls` requeues only kind `download` under 3 attempts (2.7, 2.8).
- New count columns replace `entry_count`: `parsed_count`, `stored_count`, `skipped_count`, `header_lines`, plus `parser_version` (2.13, 2.14).
- An operator CLI, `scrapers/maintenance/police_log_admin.py`, with `errors`, `reset <url>...`, and `unmatched-dispositions` (2.11, 3.7).

### Process job

- `PoliceLogPdfItem` keeps its name and carries `url_id`, `log_date`, `source_url`, and `raw_text`.
  The spider no longer parses, so `PoliceLogItem` and `test_police_log_item.py` are deleted.
- The pipeline calls `ingest_log_text` and marks the URL record `complete` in the same transaction, as today.
- A PDF that pypdf cannot read, or that yields no entries, is `error` kind `parse` with whatever text was extracted.
- A small runner, `scrapers/run_process_urls.py`, starts the crawl and exits non-zero when any URL record moved to `error` during the run (2.15).
  `scrapy crawl` alone exits 0.
- The runner takes a Postgres advisory lock on its own connection, held for the whole run, and exits with a clear message if reprocess holds it (4.11).

### Shared ingest function

`scrapers/ingest/police_log.py` is the only place that parses and writes entries.

```python
def ingest_log_text(session, pdf_url: PdfUrl, text: str) -> IngestCounts
# IngestCounts: parsed, inserted, updated, unchanged, skipped, missing, header_lines
```

- Each entry is validated with `PoliceLogRecord`, now with `extra="forbid"` and required `raw_text`, `case_number`, and `log_date`.
  An invalid entry is skipped and counted (2.4, 2.5).
- The function reads the case numbers already stored for the PDF's entries, then writes with `INSERT ... ON CONFLICT (case_number) DO UPDATE` from `record.model_dump()`.
  The update applies only when a parsed column differs and `excluded.log_date >= log_entries.log_date` (2.12).
  Inserted, updated, and unchanged are counted from the comparison in Python.
- `parser_version` is written whenever it differs, without moving `updated_at`; `updated_at` moves only when a parsed value changes (1.6, 4.9).
- Entries stored for this source URL that are not in this parse get `missing_from_parse`; the flag clears if they return (4.7).
- `header_lines` counts lines that start with a case number pattern (2.14).

### Parser

Changes in `scrapers/parsers/police_log.py`, which stays a pure function:

- `PARSER_VERSION`, an integer bumped by hand when parsing behavior changes.
- Location also matches "Vicinity of:" (3.1).
- The place code and officer code are captured instead of stripped (1.3).
- Call source comes from the "Call Source:" line when present (3.2).
- Every "Refer To" line is captured as a kind and a number (3.3).
  `reference_number` stays the first reference; new readers use `refer_to`.
- The disposition list moves to `scrapers/parsers/dispositions.py` and gains every value found in the stored PDFs (3.5).
  The parser sets `disposition_unmatched` when none matches (3.6).
- Changing the disposition list includes a parser version bump and a reprocess, because data check 14.3 fails the daily build while older entries still carry the new value inside their type.

### Reprocess

`scrapers/maintenance/reprocess_police_logs.py --from DATE --to DATE | --all`.
It is a script and not a spider because nothing is downloaded.

- It reads URL records that are `complete`, or `error` with stored text, in log date order (4.1, 4.2).
- It calls `ingest_log_text` for each in its own transaction and marks a repaired `error` record `complete` (4.4).
- It takes the same advisory lock as the process runner.
  The lock covers runs from a shell as well as from Airflow.
- It does not repair the 343 entries stored before this work.
  The move to `pdf_urls` copies nothing from Mongo, so those three PDFs have no stored text; discovery adds them again, the process job downloads them, and the upsert in `ingest_log_text` updates their entries.
- It logs the counts in 4.10.

### AI backend

`scripts/normalize/backends.py`.

```python
class AiBackend(Protocol):
    name: str            # "claude_cli" or "ollama"
    model: str
    def check_ready(self) -> None                       # raises AiBackendUnavailable
    def complete(self, prompt: str, schema: dict, timeout_s: int = 300) -> dict
    # raises AiCallFailed, or AiBackendUnavailable for login and usage limit
```

- `ClaudeCliBackend` runs `claude -p` with JSON output, the schema, and the configured model, from an empty temp directory with tools disabled.
  The default model is the small Claude model, Haiku.
  It exits with an error if `ANTHROPIC_API_KEY` is set (9.2).
  The command name comes from `CLAUDE_BIN`, so tests point it at a fake executable.
- `OllamaBackend` posts to an Ollama server with the schema in its `format` field.
  It is opt-in: a compose profile that is off by default, and a default batch size of 15.
- `FakeBackend` returns scripted replies for tests.
- `check_ready` checks that the binary or server is there.
  It makes no model call; a logged-out first call already stops the run (8.9).
- Configuration: `NORMALIZE_AI_BACKEND`, `NORMALIZE_AI_MODEL`, `NORMALIZE_BATCH_SIZE`.
- Open detail: telling a login or usage-limit failure from an ordinary one depends on what the CLI prints.
  The task captures real output; until then the rule is a best guess and the PR says so.

### Normalization job

`scripts/normalize/`, run as `python -m normalize.job [--field incident_type|location] [--redo]`.

```
job.py         find waiting values, batch, call, check, store, log the summary, set the exit code
prompts.py     prompt text, PROMPT_VERSION per field, answer models
checks.py      pure functions that sort an answer into accepted, discarded, missing
backends.py    AiBackend and its implementations
geocode.py     the geocode job
evaluate.py    the evaluation command
eval/          incident_types.jsonl, locations.jsonl, results.md
```

Flow for each field:

1. Select distinct raw values with no row, or with a row that has no value and fewer than 3 failed attempts.
2. Fold case and spacing into a key and group by it.
   A new raw value whose key already has a normalization copies the value and its source with no AI call (5.3).
3. Batch up to 50 groups per call.
   Each field gets 5 calls per run, and calls a field does not use pass to the other (9.6).
4. Check the reply, store accepted items with `source = 'ai'`, and append each to `ai_answers`.

Answer checking:

- The answer shape is one Pydantic model per field, and its JSON schema is what the backend receives, so the schema sent and the validation applied are one definition.
  The incident type model reuses `IncidentCategory` from `scripts/models/incident_category.py`.
- `checks.py` then applies the set rules: drop items whose raw value was not sent or came back twice, report missing ones, drop type names containing a listed abbreviation as a whole word, and snap a name to an existing one that differs only in case or spacing (8.3, 8.4, 5.6, 5.7).
- Only discarded and missing values get a failed attempt (8.6).
- An item with `unsure` set is stored with `needs_review` (8.5).

Writes are an insert or `UPDATE ... WHERE source IS DISTINCT FROM 'human'`, so a human row cannot be overwritten (7.9).
A redo updates each `ai` row when its new valid item arrives, so the old value stands until then (7.11).

The three old scripts and their tests are deleted with the migration that drops `subcategory`, one pull request earlier, since they stop working at that point: `scrapers/maintenance/categorize_incident_types.py`, `scripts/export/export_incident_types.py`, `scripts/ingest/import_incident_categories.py` (7.10).

### Prompts and answer schemas

Each prompt has a version string stored on every row and log line it produces.

Incident type prompt, in outline:

- The task: give each dispatch incident type a category and a short plain name for a resident reading a town website.
- The five categories with one line each, from the table below.
- Rules: plain words, abbreviations spelled out, reuse a name from the existing list when one fits, set `unsure` when guessing.
- The normalized type names already in use.
- The raw values.

```json
{
  "items": [
    {
      "raw": "MV Complaint",
      "category": "Traffic",
      "normalized_type": "Motor vehicle complaint",
      "unsure": false
    }
  ]
}
```

Location prompt, in outline:

- The task: turn each police log location in Lebanon, NH into a clean address and say what kind of place it is.
- The four kinds with an example each.
- Rules: keep house numbers, write intersections as "A St and B St", give a `geocode_query` a map search would find, never invent a house number, set `unsure` when guessing.

```json
{
  "items": [
    {
      "raw": "HANNAFORD'S MARKET - MARKET ST",
      "kind": "place",
      "normalized_address": "Hannaford, Market St",
      "geocode_query": "Hannaford, Market St, Lebanon, NH",
      "street": "Market St",
      "unsure": false
    }
  ]
}
```

Categories and what a resident sees:

| Category | Shown as | Covers |
|---|---|---|
| Police | Police | Crimes, disturbances, welfare checks, alarms, warrants. |
| Traffic | Traffic | Crashes, traffic stops, road hazards, parking. |
| Fire | Fire | Fire department calls. |
| EMS | Medical | Medical emergencies, overdoses, mental health calls. |
| Administrative | Records and notices | Log notes, broadcasts, paperwork service, records requests. |

The stored value is the category.
The "Shown as" label is the recommendation for the frontend.

### Locations package and geocode job

`geocode_nominatim` moves from `api/geocoding.py` into a shared workspace package, `shared/locations`, used by the admin API and the jobs.

```python
def geocode(query: str) -> GeocodeResult | None     # lat, lng, precision: "exact" | "approximate"
def in_city_bounds(lat: float, lng: float) -> bool
def public_location(kind, normalized_address, lat, lng) -> PublicLocation
```

- `public_location` is the one place that works out block level: it reads the leading house number from the normalized address when the kind is `address`, rounds it down to the hundred, drops it when under 100, and rounds coordinates to 3 places (11.6, 11.7).
  It runs whenever a location row is saved, by a job or by the admin API (6.11).

The geocode job, `python -m normalize.geocode`, is its own task so that AI calls and geocoding each fit the 60 minute limit.

- It takes `ai` locations that have a normalized address and no coordinates, fewer than 3 attempts, and are not bare highways (6.3).
- A place code that already has coordinates on another row supplies them, with `geocoded_via = 'place_code'` (6.2).
- Otherwise it tries `geocode_query`, then the street alone, which gives an `approximate` result (6.9).
- A limiter holds requests to 1 per second, and the job stops at 600 requests per run (6.7, 6.8).
- A result outside the city bounds is discarded (6.4).
- After 3 misses the row gets `needs_review` (6.6).
- It never touches a row whose source is `human` (6.10).

### Admin API

Changes go in `api/services/categories.py` and `api/services/addresses.py`; the routers stay thin and no third router is added.

```
GET    /api/categories?source=&needs_review=&normalized=     Page[...], with entry counts (7.3, 7.4)
PATCH  /api/categories/{raw_incident_type}                   category, normalized_type (7.5 to 7.7)
DELETE /api/categories/{raw_incident_type}                   hand back to AI (7.12)

GET    /api/addresses?source=&needs_review=&normalized=
PATCH  /api/addresses/{raw_address}                          normalized_address, kind, optional lat, lng (7.5, 7.8)
DELETE /api/addresses/{raw_address}
```

- PATCH and DELETE use `require_admin`.
- A PATCH sets `source = 'human'` and clears `needs_review`.
  The AI's answer is already in `ai_answers`, so nothing else is copied (7.6, 7.13).
- Coordinates Connor types get `geocoded_via = 'manual'`.
- The categories list keeps a `subcategory` field that mirrors `normalized_type`, so the current admin screen keeps showing a value.
  It is removed when the admin screen is rebuilt.
- Tests cover a raw value with a slash and an apostrophe, such as "911 Hang-Ups/Abandoned Calls".

### Consumer models (dbt)

A dbt project, `transform/`, using dbt-postgres, as its own workspace member so its dependencies stay out of the scrapers and the API.
Models build into a `marts` schema as views, so a correction Connor saves shows in the incidents API on the next request, with no build in between (10.6).

```
models/
  staging/
    stg_log_entries.sql          entries that are incidents: parse_error not set
    stg_incident_types.sql       incident_type_categories, with a folded key
    stg_locations.sql            address_normalizations, with a folded key
  marts/
    incidents.sql                one row per incident, raw and normalized side by side
    public_incidents.sql         incidents in the public window, public columns only
    public_addresses.sql         today's addresses.json shape, from public_incidents
    public_stats.sql             counts by category, type name, and weekday
```

- `incidents` left-joins entries to both lookup tables, so an entry with no normalization has empty normalized columns (8.12).
- `public_incidents` selects from `incidents`: the 90 day window from the newest log date, the public columns, the stored `public_location` and public coordinates, and empty values for the held-back fields (11.2 to 11.10).
- The incidents and stats API read `marts.incidents` through a read-only SQLAlchemy mapping on its own metadata, outside `Base`, so Alembic's drift check does not see it.
  `sync_es.py` reads `marts.incidents`.
- Postgres will not let a migration drop or retype a column a view reads.
  So the order is always: drop the `marts` schema with cascade, run `alembic upgrade head`, run `dbt run`.
  The `migrate` service and the test fixture both follow it, and a test proves a migration that drops a column a model uses still upgrades.
  `report-gen` becomes plain selects from the three public models and drops its own joins and its 2,000 row cap.
- A paid tier later is another model over `incidents` with a different filter.

dbt tests are the data checks in requirement 14:

| Test | On | Criterion |
|---|---|---|
| Coordinates inside the city bounds unless `geocoded_via = 'manual'` | `stg_locations` | 14.2 |
| No raw incident type ends with a listed disposition | `stg_log_entries`, against a seed of the disposition list | 14.3 |
| `accepted_values` on category | `stg_incident_types` | 14.4 |
| `unique` and `not_null` on case number | `incidents` | 14.4 |
| Every row inside the public window | `public_incidents` | 14.5 |
| `officer` is empty | `public_incidents` | 14.5 |
| No public location of kind `address` starts with a number that is not a multiple of 100 | `public_incidents` | 14.5 |

The disposition seed is generated from `dispositions.py` by a small script that runs before each dbt build, and it is not committed, so the list lives in one place.

### Evaluation

`python -m normalize.evaluate --field incident_type|location [--backend ...] [--model ...]`.

- The evaluation set is two JSONL files in `scripts/normalize/eval/`, each line a raw value and its expected values.
  It starts from the distinct values in the three stored PDFs: 92 incident types and 176 locations to draw from.
  A draft is labeled with AI help and then checked line by line by Connor, since a person has to decide what is right.
- The draft labels come from a different model and prompt than the one being scored, and `results.md` says which, so the first score does not flatter the default backend.
- Known limit: the set comes from the same three PDFs the prompts were written against.
  Lines from new PDFs are added after the backfill.
- The command runs the same prompt building, backend, and `checks.py` as the job, and neither reads nor writes the database (15.2).
  The list of type names already in use is a fixed file stored with the set.
- It prints accuracy per field, the discarded and unsure counts, and each wrong item (15.3 to 15.5), comparing text without regard to case or spacing (15.6).
- Each recorded run adds a line to `eval/results.md`: date, backend, model, prompt version, scores.
- A change to a prompt, the default model, or the default backend includes a new line there.
- Later, rows in `ai_answers` that Connor corrected can be added to the set; that is a follow-up.

### Schedule

`dags/specs.py` describes one command per DAG, with triggers that fire only on success.
The police log chain needs steps that keep going after a failure, so it is a plain DAG file, `dags/police_log.py`, next to the specs.
`DagSpec` and its builder stay as they are.

One DAG, `police_log`, daily, replaces the `discover_urls` and `process_urls` specs:

```
discover ─► process (limit 100) ─► normalize ─► geocode ─► dbt build ─► sync_es ─► watcher
```

- Process, normalize, and geocode failures do not stop the stages after them; those tasks use `all_done`.
  A failed dbt build stops the sync (12.6).
- A final watcher task fails the run when any task failed, so a bad day is red (12.7).
- One run at a time, a 60 minute timeout on each task (12.4, 12.5), and an Airflow pool of size 1 shared with reprocess.
- A manual DAG, `police_log_reprocess`, with date parameters, wraps the reprocess script.
- A one-shot `migrate` service in compose drops `marts`, runs `alembic upgrade head`, then `dbt run`, and the Airflow services wait for it (12.8).

Running AI in the schedule:

- The `claude` CLI is installed in the Airflow image and reads a token from `claude setup-token` passed through `.env`.
  Connor creates the token once and renews it when it expires.
- This cannot be verified from the build sandbox, so the task ends with a manual check: one real call from inside the container.
- Fallback with no code change: run the same command from host cron.

The public export is not scheduled (12.9).
The export runs at deploy time: `deploy.sh` runs `report-gen` against the public models before each build.
The files in `frontend/web/public/data` are gitignored and not committed.

## Data models

### `log_entries`

| Column | Type | Notes |
|---|---|---|
| `log_date` | date, NOT NULL | Backfilled in the migration from the URL record's `log_date`, else `reported_at::date`. The migration fails if any row is still null. |
| `place_code` | text | For example `L HANNAF`. |
| `officer_code` | text | For example `SMN`. |
| `refer_to` | jsonb | List of `{kind, number}`. |
| `disposition_unmatched` | boolean | Default false. |
| `missing_from_parse` | boolean | Default false. |
| `parser_version` | integer | |
| `created_at`, `updated_at` | timestamp | `created_at` backfilled from `scraped_at`. |

`case_number` becomes NOT NULL; the live table has no nulls.

### `pdf_urls`

Adds `error_kind`, `parsed_count`, `stored_count`, `skipped_count`, `header_lines`, `parser_version`.
Drops `entry_count`.

### Provenance columns

One SQLAlchemy mixin adds these to both lookup tables.

| Column | Type | Notes |
|---|---|---|
| `source` | text | `ai` or `human`, with a check constraint. Null while a value waits. |
| `ai_backend`, `model`, `prompt_version` | text | Describe the last AI answer. They stay when a human takes over the value. |
| `needs_review` | boolean | The review mark. |
| `failed_attempts` | integer | Default 0. |

A row may exist with no normalized value: that is where failed attempts and the review mark live for a raw value AI has not answered.
Deleting the row hands the value back to AI and clears the count in one step (7.12).

### `incident_type_categories`

Adds `normalized_type` and the provenance columns.
`category` becomes nullable.
`subcategory` is dropped; the table is empty.

### `address_normalizations`

Adds `kind`, `place_code` (indexed), `street`, `geocode_query`, `geocode_attempts`, `coordinate_precision`, `public_location`, `public_lat`, `public_lng`, and the provenance columns.
The `geocoded_via` check widens to `manual`, `nominatim`, `place_code`.
`source` says who owns the row; `geocoded_via` says how its coordinates were found.

### `ai_answers`

Append-only.

| Column | Type |
|---|---|
| `id` | integer |
| `field` | text: `incident_type` or `location` |
| `raw_value` | text |
| `answer` | jsonb |
| `ai_backend`, `model`, `prompt_version` | text |
| `created_at` | timestamp |

Every accepted AI answer is logged here.
A human edit overwrites the current value, and the AI's answer stays in the log with its model and prompt version (7.13).

### Migrations

Three: `log_entries` and `pdf_urls` columns; the lookup tables and `ai_answers`; nothing for the consumer models, which dbt owns.
Each lands with the pull request that uses it.

## Error handling

| Failure | What happens | Criteria |
|---|---|---|
| Download fails or times out | Errback marks `error` kind `download`; retried until 3 attempts. | 2.7, 2.10 |
| PDF unreadable or yields no entries | `error` kind `parse`, text stored, waits for reprocess. | 2.8 |
| One entry invalid | Skipped and counted; the rest of the PDF is stored. | 2.4 |
| Transaction fails | Rollback, `error` kind `save`; other PDFs unaffected. | 2.3, 2.6 |
| Process dies mid-PDF | Claim expires after 120 minutes; the attempt was counted at claim. | 2.9 |
| AI call errors or times out | Nothing stored; values wait; no failed attempt counted. | 8.1, 8.6 |
| AI answer empty or off-schema | Nothing stored from that call. | 8.2 |
| AI item missing, duplicated, or invalid | Item dropped; that value gets a failed attempt; 3 gives a review mark. | 8.3, 8.4, 8.7 |
| AI says unsure | Stored with a review mark. | 8.5 |
| Backend logged out or at its usage limit | No more AI calls this run. | 8.9 |
| Every AI call fails | Job exits non-zero; later stages still run. | 8.11, 12.6 |
| Geocoder miss or failure | Address kept, coordinates untouched, attempt counted. | 6.5, 6.6 |
| Coordinates outside the city bounds | Discarded. | 6.4 |
| A dbt test fails | Build fails and names the test and row count; the sync does not run. | 14.1, 14.6, 12.6 |

## Testing strategy

One mechanism for database tests, replacing the three that exist (`TEST_DATABASE_URL` in the migration test, `FakeSession` in the scrapers tests, mocked sessions in the API tests):

- `conftest.py` sets `POSTGRES_DB=app_test` before anything imports the client, and stops the run if the name does not end in `_test` (13.2).
  The check runs before any connection.
- A session fixture creates `app_test` if missing and runs `alembic upgrade head`.
  A separate fixture, asked for only by API and dbt tests, runs `dbt run` so the `marts` views exist.
- Each test rebinds the existing sessionmaker to one connection inside an outer transaction, `SessionLocal.configure(bind=connection, join_transaction_mode="create_savepoint")`, and restores it after, so code under test can commit and the test still rolls back (13.3).
  No production code changes for this.
- The fixtures are a pytest plugin in `shared/postgres` that the scrapers, scripts, and API suites load.
- The migration test keeps the branch's approach of running Alembic inside a rolled-back connection, and moves onto this mechanism (13.4).
- `FakeSession` is deleted when the pipeline tests move; the three cases it covers are ported to the real database (13.6).
- If Postgres is not running, tests fail with a message; they are not skipped.
  The pre-push hook therefore needs Postgres up.

Other tests:

- Parser: one text fixture and test per fixed gap, cut from the three stored PDFs.
- Backend contract tests: one parametrized suite over `FakeBackend`, `ClaudeCliBackend` with a fake executable, and `OllamaBackend` with a stubbed server (9.3).
- Normalization and geocode jobs: `FakeBackend` and a fake geocoder; no real AI call and no request to Nominatim (13.5).
- dbt: `dbt build` against `app_test` with seeded rows that should pass, and one seeded bad row per data check that should fail it.
- DAG: structure tests on the spec, in the style of `dags/tests/test_specs.py`.
- Evaluation: the scoring functions are unit tested with a fake backend; the real run is manual (15.7).

QA after each pull request: the suites, then a real run against `app_test`, never `app`.
For the AI pull request that includes one real batch of 10 values and one evaluation run.

## Decisions

### Rules where the vocabulary is closed, AI where it is open

The parser splits type from disposition with a list in the repo and flags what it cannot split.
AI names and categorizes incident types and cleans locations.

- Rejected: AI splits type from disposition, for all entries or only flagged ones.
  Dispositions are a closed set of about 40 values that a rule reads exactly and for free.
  An AI split would be a second source of dispositions that every consumer has to merge.
  Adding the missing value to the list and reprocessing fixes the entry and every later one.
- Rejected: rules for incident types.
  92 distinct values in 3 days and no fixed list; a rule table would need constant upkeep.

### Normalize distinct values, not entries

- Rejected: normalized columns on `log_entries`.
  Roughly 76,000 entries reduce to a few thousand distinct strings, so per-entry calls would waste the Max plan's limits, and every correction would have to fan out to its entries.

### Extend the two lookup tables

- Rejected: one generic table keyed by field and raw value.
  The payloads differ, so it means sparse columns or a JSON blob and loses the checks.
- Rejected: a `places` table keyed by place code.
  More correct, but a `place_code` column covers reuse of coordinates at a fraction of the size.

### One ingest function for process and reprocess

- Rejected: a reprocess spider, or parsing in the spider as today.
  Two code paths would drift, and nothing needs downloading.

### Answers are checked in code, never trusted

Structured output gives the shape; Pydantic models and `checks.py` enforce the content.

- Rejected: parsing free text with a regex, as the old script does.
- Rejected: storing a batch without set checks.
  An echoed raw value that was never sent would create a normalization for a string that does not exist.

### Human corrections win, and AI answers are logged

- Rejected: overwrite on conflict, as both old scripts do.
- Rejected: `ai_value` columns beside each normalized value.
  They keep only the latest AI answer, so a redo erases the one before it.
  The append-only log keeps every answer by prompt version, which is what the evaluation set grows from.

### `claude -p` with Haiku by default, Ollama opt-in, behind one interface

- Rejected: calling the CLI straight from the job.
  Tests would patch `subprocess`, and a second backend would mean a rewrite.
- Rejected: Ollama as the default.
  Docker on macOS gives containers no GPU, so a 50-item batch would likely take several minutes on CPU, and small models drop items and alter the strings they should echo.
  Those figures are estimates, which is why the evaluation command exists: the local model is used for a scheduled run only after its score is recorded.
- Rejected: any paid API.

### dbt builds the consumer models

The admin API, the search sync, and the public export disagreed about what an incident is because each wrote its own query, one of them in Rust.
dbt gives one definition in staged SQL models, with the data checks as tests beside them and lineage docs for free.

- Rejected: one plain Postgres view in an Alembic migration.
  It is one file and no new tool, and it would work.
  But changing a view means a migration, the data checks would need their own home, and three stacked views in migrations are hard to read.
  dbt is also a tool worth knowing and showing.
  dbt has two costs of its own: every migration run must drop and rebuild the views, and the marts mapping has to sit outside the ORM's metadata.
- Rejected: dbt tables instead of views.
  A correction would not show in the admin until the next build.
- Rejected: the same join written in each consumer, as today.

### Tests against a real database

- Rejected: mocked or fake sessions.
  The tests on main pass while the lost-rows bug exists, and the branch's `FakeSession` still never touches Postgres.

### The pipeline base class is not built

The lost-rows bug it was meant to fix is already fixed in all five pipelines on `fix/integration`, and the police pipeline no longer fits a per-item base.
Tidying the other four is a follow-up.

## Open questions

1. **Do 2025 PDFs use the same layout?**
   The parser is proven only on May 2026.
   The header-line check (2.14) will show it during the backfill.
2. **How the CLI reports a login or usage-limit failure.**
   Needed for 8.9; Connor may have to run one command and paste the output.
3. **The token for the scheduled AI call.**
   Connor runs `claude setup-token` once and puts the token in `.env`.
4. **The officer column on the public site.**
   The export writes an empty `officer`, so the officer column and filter in `incidents-table.tsx` will have nothing to show until the frontend changes.
5. **Who labels the evaluation set.**
   The plan is an AI-drafted set that Connor checks line by line, about 150 lines.
