# Police log pipeline: design

**Status:** In progress
**Created:** 2026-11-06
**Updated:** 2026-11-13

## Overview

This design is written as changes on top of the `fix/integration` and `fix/url-queue` branches, which ship first.
It covers all sixteen requirements.

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
Postgres holds every parsed, structured field.
Raw, unparsed source lives in the MongoDB raw source archive: the original PDFs, each entry's raw text and unsplit reason and action text, and the AI call records.
Reprocess re-extracts text from the archived PDFs; Postgres keeps the content hash as the reference.
Parsed raw values stay on `log_entries` and are never rewritten.
Normalized values live in the two existing lookup tables, each row carrying who produced it.
A normalization job fills them, and a separate job geocodes locations.
The normalization job is a workflow, not an agent: code loads the batch, fixed rules settle the exact matches, and the model sees only the leftovers.
The model gets no tools and no database, returns schema JSON, and code checks and writes every answer.
Connor's edits go through the admin API, are marked `human`, and no job overwrites them.
dbt builds the consumer models, runs the data checks, and gives the admin API, admin search, and the public export one definition of an incident.
Admin search is a Postgres query over those models, using full-text search and trigram matching, with no separate search index.
The public export stays a manual step.
An evaluation command scores each backend, model, and prompt version against a labeled set.

## Architecture

```
city page ──► discover spider ──► pdf_urls (pending)
                                      │ claim (claimed_at, attempts)
                                      ▼
                    process spider: download, extract text ──► archive middleware ──► Mongo raw_sources (PDF bytes)
                                      │ one PoliceLogPdfItem per PDF                                    │
                                      ▼                                                                 │
            pipeline ──► ingest_log_text() ──► log_entries (raw values)                                 │
                              ▲                        │                                                │
     reprocess script ────────┴── pypdf ◄──────────────┼────────────────────────────────────────────────┘
     (archived PDF, no download)                       │ distinct raw values
                                                       ▼
              normalize job, by hand on Connor's Mac ──► rule pass (shared/locations): exact matches stored, no AI
                                           │
                                           │ leftovers, street list, schema (no tools, no database)
                                           ▼
                                    AI backend (claude -p, or Ollama) ──► JSON answer ──► Mongo ai_calls (every call)
                                           │
                                           │ back in the job: Pydantic, checks.py, upsert (never over human)
                                           ▼
                 incident_type_categories, address_normalizations ◄── admin API (source = human)
                                           ▲
                                    geocode job ──► Nominatim (bounds, 1 per second)     [daily DAG]
                                           │
                                           ▼
                        dbt: staging ──► incidents ──► public 90 day models, with tests   [daily DAG]

      Daily DAG in Airflow: discover ─► process ─► geocode ─► dbt build.
      The normalize job is not in it; Connor runs it on his Mac, and the DAG uses what is normalized so far.
                              ┌────────────┴────────────────┐
              incidents API and admin search          report-gen (public export)
              (Postgres full-text and pg_trgm)

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
- New count columns replace `entry_count`: `parsed_count`, `stored_count`, `skipped_count`, `header_lines` (2.13, 2.14).
- `content_hash`, the SHA-256 of the PDF bytes that were ingested, is the reference to the archived version (1.4).
- `parser_version` and `extractor_version` record what produced the PDF's entries (1.7).
- An operator CLI, `scrapers/maintenance/police_log_admin.py`, with `errors`, `reset <url>...`, and `unmatched-dispositions` (2.11, 3.7).

### Process job

- `PoliceLogPdfItem` keeps its name and carries `url_id`, the extracted text, the content hash, and whether the archive stored the PDF.
  The spider computes the hash with the archive's own `content_hash(source, body)` from `shared/mongo`, so `pdf_urls.content_hash` always matches an archived version.
  The archived flag comes from `response.meta["archived"]`, which the archive middleware sets after writing the PDF, one at a time, before the callback runs.
  A missing flag, as when `RAW_ARCHIVE_ENABLED` is off, counts as not archived.
  The pipeline reads the log date and source URL from the `pdf_urls` row.
  The spider no longer parses, so `PoliceLogItem` and `test_police_log_item.py` are deleted.
- The archive middleware stores the PDF bytes in Mongo on the way in; Postgres stores neither the bytes nor the text (1.4).
- The pipeline calls `ingest_log_text` and marks the URL record `complete` in the same transaction, as today.
- A PDF that parses to no entries, or to no valid entry, is `error` kind `parse`; a failed save is kind `save`.
  Both wait for a reprocess of the archived original (2.8).
- If the archived flag is false, those two become kind `download` instead, so the PDF is downloaded and archived again (2.8).
- A PDF that pypdf cannot read is `error` kind `download` and is retried.
- A small runner, `scrapers/run_process_urls.py`, starts the crawl and exits non-zero when any URL record moved to `error` during the run (2.15).
  `scrapy crawl` alone exits 0.
  The runner also exits non-zero when the crawl itself breaks, for example when it cannot claim URLs.
- The runner takes a Postgres advisory lock on its own autocommit connection, held for the whole run, and exits with a clear message if reprocess holds it (4.11).

### Shared ingest function

`scrapers/ingest/police_log.py` is the only place that parses and writes entries.

```python
def ingest_log_text(session, pdf_url: PdfUrl, text: str) -> IngestCounts
# IngestCounts: parsed, inserted, updated, unchanged, skipped, missing, header_lines
```

- Each entry is validated with `PoliceLogRecord`, now with `extra="forbid"` and required `case_number` and `log_date`.
  The parser cuts each entry's block of text to read its fields; the block and the unsplit reason and action text go to the archive, not to Postgres.
  An entry's log date is the URL record's, or the PDF's "For Date:" line when the URL record has none.
  An invalid entry is skipped and counted (2.4, 2.5).
- The function reads the case numbers already stored for the PDF's entries, then writes with `INSERT ... ON CONFLICT (case_number) DO UPDATE` from `record.model_dump()`.
  The update applies only when a parsed column differs and `excluded.log_date >= log_entries.log_date` (2.12).
  When an older PDF repeats a case number, the stored row is left fully alone, including its parser version.
  Inserted, updated, and unchanged are counted from the comparison in Python.
- `parser_version` on the entry is written whenever it differs, without moving `updated_at`; `updated_at` moves only when a parsed value changes (1.6, 4.9).
- The URL record also carries the parser and extractor versions of its last ingest (1.7).
- After the transaction commits, the pipeline writes one `police_log_entry_text` version per entry to the archive, best-effort, keyed by case number (1.4).
  A failed write is logged and counted.
  With `RAW_ARCHIVE_ENABLED` off, no entry texts are written.
- Entries stored for this source URL that are not in this parse get `missing_from_parse`; the flag clears if they return (4.7).
- `header_lines` counts lines that start with a case number pattern (2.14).

### Parser

Changes in `scrapers/parsers/police_log.py`, which stays a pure function:

- `PARSER_VERSION`, an integer bumped by hand when parsing behavior changes.
  It starts at 1 in PR 2, because ingest writes it, and PR 3 bumps it.
- `EXTRACTOR_VERSION` is `pypdf.__version__`.
  A pypdf bump in `uv.lock` can change whitespace or word order in the extracted text, so it counts as a parser change: bump `PARSER_VERSION` in the same pull request and reprocess (3.3).
  A comment next to pypdf in `scrapers/pyproject.toml` says so, where whoever merges a Dependabot bump will see it.
- Location also matches "Vicinity of:" (3.1).
- The place code and officer code are captured instead of stripped (1.3).
- Every "Refer To" line is captured as a kind and a number in `refer_to` (3.8).
  `reference_number` stays the first reference.
- Call source comes from the "Call Source:" line when present (3.2).
- The disposition list moves to `scrapers/parsers/dispositions.py` and gains every value found in the stored PDFs (3.5).
  When none matches, the parser keeps the unsplit text as the raw incident type and sets `disposition_unmatched` (3.6).
- Changing the disposition list includes a parser version bump and a reprocess, because data check 14.3 fails the daily build while older entries still carry the new value inside their type.

### Reprocess

`scrapers/maintenance/reprocess_police_logs.py --from DATE --to DATE | --all`.
It is a script and not a spider because nothing is downloaded.
It is also the archive's replay for police log PDFs; the archive spec's replay command handles parcel pages only.

- It reads URL records that are `complete` or `error`, in log date order (4.1, 4.2).
- For each, it takes the newest archived version, extracts text with pypdf, and calls `ingest_log_text` in its own transaction, then records the content hash and versions and marks a repaired `error` record `complete` (4.4).
  It writes the entry texts again; at the same parser version, unchanged ones only move their seen count.
  A URL with no archived PDF body but a `police_log_text` version is reparsed from that text.
- A record with no archived version goes back to `pending` and is counted (4.12).
- It checks the archive is reachable before it starts, and exits with an error if not (4.13).
- It takes the same advisory lock as the process runner.
  The lock covers runs from a shell as well as from Airflow.
- It does not repair the 343 entries stored before this work.
  Those three PDFs were never archived; discovery adds them again, the process job downloads and archives them, and the upsert in `ingest_log_text` updates their entries.
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

The pattern is a workflow, not an agent (see Decisions).
The backend is a pure function from a prompt and a JSON schema to an answer.
It never sees a database connection, a file, or a tool.

- One AI call is one batch.
  For `ClaudeCliBackend` that is one `claude -p` subprocess per batch, which ends before the answer is checked.
- `ClaudeCliBackend` runs `claude -p` with structured JSON output against the schema and the configured model.
  It runs with every tool turned off, from a fresh empty temporary working directory that is deleted afterwards, and under a timeout (8.1, 9.8).
  It does not load the project's or the user's settings, hooks, or MCP servers.
  Only the prompt and schema go in, and only stdout comes back.
- The exact CLI flags for structured output, turning tools off, the model, and skipping settings and MCP servers are confirmed in task 13 against `claude --help` and one real call.
  This design doesn't name them.
- The default model is the small Claude model, Haiku.
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

`scripts/normalize/`, run by Connor on his Mac from the repo root as `uv run python -m scripts.normalize.job [--field incident_type|location] [--redo]` (see "Running the normalization job on the Mac").
Task 15 confirms the module path matches the `scripts` package layout.

```
job.py         find waiting values, rule pass, batch, call, check, store, log the summary, set the exit code
rules.py       the rule pass for locations, built on shared/locations canonical rules
streets.py     builds the street list from parcel locations, and its version
prompts.py     prompt text, PROMPT_VERSION per field, answer models
checks.py      pure functions that sort an answer into accepted, discarded, missing
backends.py    AiBackend and its implementations
geocode.py     the geocode job
evaluate.py    the evaluation command
eval/          incident_types.jsonl, locations.jsonl, results.md
```

Flow for each field:

1. Select distinct raw values with no row, or with a row that has no value and fewer than 3 failed attempts.
   A raw value with a stored value is never selected again, so each one goes to AI at most once (5.4, 6.13).
   Only `--redo` sends stored values again, and only those whose `prompt_version` isn't the current one (7.14).
2. Group by a key.
   Incident types use case and spacing folded.
   Locations use the canonical address from `shared/locations`, which also folds suffix and direction spellings.
   A new raw value whose key already has a normalization copies the value and its source with no AI call (5.3).
3. Locations only: the rule pass, which makes no AI call (6.14 to 6.18).
   - A canonical address that is a house number followed by a street on the street list is stored as kind `address`.
   - Two streets on the list joined by `and`, `&`, or `/` are stored as kind `intersection`.
   - A raw value whose place code already has a `place` normalization with no review mark copies its normalized address and kind.
   - These rows get `source = 'rule'`, `prompt_version = 'rules-<RULES_VERSION>'`, and a `geocode_query` built from the normalized address.
   - Anything else, including a bare street name, is a leftover.
4. Batch up to 50 leftover groups per call.
   Each field gets 5 calls per run, and calls a field does not use pass to the other (9.6).
   The location prompt carries the street list (6.20, 6.21).
   If the street list is empty, the job makes no location AI calls that run and logs an error (6.23).
5. Parse stdout with the field's Pydantic answer model, run `checks.py`, then store accepted items with `source = 'ai'`, the call's `ai_call_id`, and the effective prompt version.
6. Write one `ai_calls` document per call, failed or not, through the archive's best-effort writer (8.13).
   If Mongo is down, the normalizations are still stored and the lost call records are counted (8.14).

The job is the only code that reads raw values or writes normalizations (9.9).
Between steps 4 and 5 there is no database handle in the backend's reach.
A crash between the call and the write loses only that call's answer: nothing is half written, and the values are still waiting next run.

### Street list

- `streets.py` builds it from `properties.location`.
  It strips the house number and any unit, applies the canonical address rules, and keeps the distinct streets in sorted order (6.20).
- Expected size: a few hundred streets, from about 5,000 parcels.
  That's an estimate; task 14 measures the count and the tokens it adds to a prompt.
- It's built once per run, in memory, and not stored in its own table.
  Its version is the first 8 hex digits of the SHA-256 of the sorted list joined by newlines.
- The location prompt's effective version is `<PROMPT_VERSION>+streets-<hash>`.
  That value goes on every `ai_calls` document and in each row's `prompt_version` (6.24).
  A weekly VGSI scrape that adds a street changes the version.
  That moves no row, since only `--redo` acts on older versions.
- The street list depends on the VGSI scrape having run.
  An empty `properties` table gives an empty list, and 6.23 applies.

Answer checking:

- The answer shape is one Pydantic model per field, and its JSON schema is what the backend receives, so the schema sent and the validation applied are one definition.
  The incident type model reuses `IncidentCategory` from `scripts/models/incident_category.py`.
- `checks.py` then applies the set rules: drop items whose raw value was not sent or came back twice, report missing ones, drop type names containing a listed abbreviation as a whole word, and snap a name to an existing one that differs only in case or spacing (8.3, 8.4, 5.6, 5.7).
- For locations, `checks.py` also compares the answer's `street`, in canonical form, with the street list.
  A street not on the list is stored with `needs_review`, not discarded, because a state road or a neighboring town's street can be right (6.22).
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
- The street list: "Use a street from this list when the location is on one; leave `street` empty if none fits."
- The raw values, all of them leftovers that the rule pass didn't settle.

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

# shared/locations/canonical.py, the one implementation of the canonical address rules
RULES_VERSION: str
def canonical_address(raw: str) -> str              # case, spacing, punctuation, suffix and direction spellings
def split_house_number(canonical: str) -> tuple[str | None, str]   # ("12", "MAIN ST"), or (None, "MAIN ST")
def strip_unit(canonical: str) -> tuple[str, str | None]           # ("12 MAIN ST", "UNIT 3")
```

- The suffix and direction spellings are a data file in the package, `shared/locations/street_suffixes.csv`, based on the USPS street suffix abbreviations.
  A change to the file or the functions bumps `RULES_VERSION`.
- The functions are pure, with no database and no network, so they're tested on their own with known spelling pairs.
- This is the implementation the address entity spec's canonical rules refer to.
  That spec's design (on `spec/address-entity`) planned a dbt macro, and has to be updated to use these instead (open question 7).


The geocode job, `python -m scripts.normalize.geocode`, runs in the daily DAG. It makes no AI call, so it needs no Claude login.
It geocodes whatever has been normalized so far, so a value Connor normalizes today gets coordinates on the next daily run, or right away if he runs the same command on his Mac.

- It takes `ai` and `rule` locations that have a normalized address and no coordinates, fewer than 3 attempts, and are not bare highways (6.3).
- It takes the police log lock for its run, so it never overlaps the normalization job (16.2, 16.3).
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
  The AI's answer is already in its `ai_calls` document, so nothing is copied (7.6, 7.13).
- Coordinates Connor types get `geocoded_via = 'manual'`.
- The categories list keeps a `subcategory` field that mirrors `normalized_type`, so the current admin screen keeps showing a value.
  It is removed when the admin screen is rebuilt.
- Tests cover a raw value with a slash and an apostrophe, such as "911 Hang-Ups/Abandoned Calls".

### Consumer models (dbt)

A dbt project, `transform/`, using dbt-postgres, as its own workspace member so its dependencies stay out of the scrapers and the API.
Models build into a `marts` schema as views, so a correction Connor saves shows in the incidents API on the next request, with no build in between (10.10).

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
- `public_incidents` selects from `incidents`: the 90 day window from the newest log date, the public columns, the public location and coordinates, and empty values for the held-back fields (11.2 to 11.10).
- A dbt macro, `public_location`, is the one place that works out block level: for kind `address` it reads the leading house number from the normalized address, rounds it down to the hundred, drops it when under 100, and rounds coordinates to 3 places (6.11, 11.6, 11.7).
  Data check 14.5 tests its output.
- The incidents and stats API and admin search read `marts.incidents` through a read-only SQLAlchemy mapping on its own metadata, outside `Base`, so Alembic's drift check does not see it.
- `report-gen` becomes plain selects from the three public models and drops its own joins and its 2,000 row cap.
- Postgres will not let a migration drop or retype a column a view reads.
  So the order is always: drop the `marts` schema with cascade, run `alembic upgrade head`, run `dbt run`.
  The `migrate` service and the test fixture both follow it, and a test proves a migration that drops a column a model uses still upgrades.
- A paid tier later is another model over `incidents` with a different filter.

### Admin search

Search is a `q` parameter on the existing incidents endpoint, `GET /api/incidents?q=...`, handled in `api/services/incidents.py` alongside the filters in 10.2.
The word matching lives in its own module, `api/services/text_search.py`, because the cross-entity search in the search spec reuses it for all nine record types.
It reads `marts.incidents`, so a saved correction shows on the next request (10.10).

- `marts.incidents` carries a `search_text` column: raw and normalized type, category, raw and normalized location, disposition, and officer, joined with spaces.
  The officer is admin-only; the public models do not carry `search_text`.
- The service splits the query into words, and every word must match the incident (10.5).
  A word matches when any of these holds:
  - it is in `to_tsvector('simple', search_text)`;
  - it has 5 or more letters and is within one edit of a word in `search_text`, by `levenshtein_less_equal(word, stored_word, 1) <= 1` from the `fuzzystrmatch` extension, which catches "Hanovr", "Hanpver", and "Mxple" (10.6);
  - it is at least 4 digits and hyphens and appears in the case number, by `ILIKE`, so "13339" finds "26-13339" but "26" does not match every 2026 case (10.7).
- The edit-distance check needs the incident's words, about 20 per row, so it is the expensive path.
  A cheap pg_trgm prefilter, `word_similarity(word, search_text) >= 0.3`, runs first, so the edit distance is only worked out for rows that are already close.
  Trigrams alone fall short of 10.6: a wrong letter in the middle of a 5-letter word, such as "Mxple" or "Maxle" for "Maple", scores 0.333, measured on Postgres 16.
  So the prefilter must never be raised above 0.333, or it drops the typos the edit distance is meant to catch.
  It only narrows rows; the edit distance decides the match.
- Swapped letters, such as "Mapel", are two edits and do not match; 10.6 does not promise them.
- "hannafords" for "HANNAFORD'S" is one edit from the stored word "hannaford" with its "s" split off, so it is covered by the same rule.
  The `simple` parser splits "26-13339" into "26" and "-13339", which is why case numbers are matched on their own.
- Words of 4 letters or fewer, such as "St", "MV", and "Main", match exactly, because one edit on a short word matches far too many rows.
- Because the service splits the words itself, `-word`, quotes, and `or` have no special meaning.
  Every word is a plain match; operators can be added later if Connor wants them.
- Order: the sum of each word's full-text rank and trigram score, with an edit-distance match counted after an exact one, then `reported_at` descending (10.9).
- Normalized address (10.8): the view joins every raw spelling to its normalized address, so matching the normalized value returns every spelling.

Speed:

- `search_text` is an expression over three tables, so no index can serve it, and every search is a sequential scan of the view.
  At 76,000 entries, about the full backlog, that should fit the timing criterion (10.11), but the fuzzy path is the risk.
- The migration enables `pg_trgm` and `fuzzystrmatch`, both contrib extensions in the postgres:16 image; no trigram indexes are added, because none would be used.
- The seeded timing test, 100,000 incidents and a five-word query that needs the edit-distance path, is the first step of the task, before the rest is built.
  Its fuzzy word is a 5-letter word with a wrong middle letter, such as "Mxple": at 0.3 that typo lets the most rows past the prefilter, so it is the case the 1 second limit has to hold for.
  The pre-push hook skips it, since wall-clock checks are flaky on a busy laptop; QA runs it.
- First fallback if it fails: index each source table on its own, with a tsvector and a trigram index on the raw columns of `log_entries` and on the normalized columns of each lookup table.
  Each word then matches entries directly, or entries whose raw type or location maps to a matching lookup row, and the per-word results are intersected.
  Every piece is indexable, both fuzzy checks then run against the small lookup tables, and 10.10 still holds.
- Second fallback: a dbt `incidents_search` table with its own index, rebuilt by the daily build.
  It loses 10.10, so it is Connor's decision.

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
- Later, `ai_calls` answers that Connor corrected can be added to the set by a script that joins the two stores; that is a follow-up.

### Schedule

`dags/specs.py` describes one command per DAG, with triggers that fire only on success.
The police log chain needs steps that keep going after a failure, so it is a plain DAG file, `dags/police_log.py`, next to the specs.
`DagSpec` and its builder stay as they are.

One DAG, `police_log`, daily, replaces the `discover_urls` and `process_urls` specs:

```
discover ─► process (limit 100) ─► geocode ─► dbt build ─► watcher
```

- There is no normalize task (12.2, 16.5).
  Geocode and the build work on whatever has been normalized so far.
  An entry whose values aren't normalized yet is still built, with empty normalized fields (8.12), and stays out of the public map until it is (11.9).
- Process and geocode failures don't stop the stages after them; those tasks use `all_done` (12.6).
  With normalize gone, the rule still holds: a failed process still runs geocode and the build, and a failed geocode still runs the build.
- A final watcher task fails the run when any task failed, so a bad day is red (12.7).
- One run at a time, a 60 minute timeout on each task (12.4, 12.5), and an Airflow pool of size 1 shared with reprocess.
- Process, reprocess, and geocode take the police log lock, and so does the normalization job on the Mac.
  If Connor is normalizing when the DAG reaches process or geocode, that task finds the lock held, fails fast with the message, and the work waits for the next run.
  So he runs the job outside the DAG's start time.
- A manual DAG, `police_log_reprocess`, with date parameters, wraps the reprocess script.
- A one-shot `migrate` service in compose drops `marts`, runs `alembic upgrade head`, then `dbt run`, and the Airflow services wait for it (12.8).

The Airflow image has no `claude` CLI and no Claude token.
That work is deferred; the `airflow-claude-cli` branch exists, unbuilt, if it's ever revisited.

### Running the normalization job on the Mac

From the repo root, after `docker compose up -d postgres mongo` and `uv sync`:

```bash
uv run python -m scripts.normalize.job              # both fields
uv run python -m scripts.normalize.job --field location
uv run python -m scripts.normalize.geocode          # optional: place today's values now
```

- It reads `.env` from the repo root like the other scripts; `.env.example` already points Postgres and MongoDB at `localhost`.
- It uses Connor's `claude` login, with no token in `.env` (16.1). The AI calls still run as in "AI backend" (9.8).
- It takes the police log lock first; if the lock is held, it exits with status 1 and says so (16.2, 16.3).
  `police_log_lock` moves from `scrapers/ingest/lock.py` to `shared/postgres` so `scripts/` can import it, with the same key.
- It logs the per-field counts in 8.10 and exits with status 1 when it can't run or every AI call fails (16.4).

Optional later: a LaunchAgent. This is a sketch for docs only, and nothing is installed by the repo.

```xml
<!-- ~/Library/LaunchAgents/com.lebanondata.normalize.plist -->
<plist version="1.0"><dict>
  <key>Label</key><string>com.lebanondata.normalize</string>
  <key>ProgramArguments</key><array>
    <string>/bin/zsh</string><string>-lc</string>
    <string>cd ~/projects/data-project &amp;&amp; uv run python -m scripts.normalize.job</string>
  </array>
  <!-- After the daily DAG has finished, so the lock is free. -->
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>/Users/connor/Library/Logs/lebanondata-normalize.log</string>
  <key>StandardErrorPath</key><string>/Users/connor/Library/Logs/lebanondata-normalize.log</string>
</dict></plist>
```

- It runs only while Connor is logged in, because a LaunchAgent lives in his user session; that is also what gives it his `claude` login.
- It runs only while the Mac is awake.
  launchd runs a missed calendar slot once at the next wake, and misses it entirely while the Mac is off.
- The login shell (`-lc`) puts `uv` and `claude` on the path.
- Failures surface three ways:
  - the log file;
  - the last exit status in `launchctl print gui/$(id -u)/com.lebanondata.normalize`;
  - the Logfire summary.

  There's no push alert. If he wants one, a wrapper can post a macOS notification on a non-zero exit, which is a small follow-up.

The public export is not scheduled (12.9).
The export runs at deploy time: `deploy.sh` runs `report-gen` against the public models before each build.
The files in `frontend/web/public/data` are gitignored and not committed.

## Data models

### `log_entries`

| Column | Type | Notes |
|---|---|---|
Adds:

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

Drops `raw_text`, `raw_reason_action`, and `scraped_at`.
The two text columns are raw source and move to the archive; the legacy import copies the 343 live rows' values there before the migration runs (archive 8.4).
The parser still cuts both for each entry; the ingest moves them into an `EntryText` before validating the record, so they reach the archive as `police_log_entry_text` and never Postgres.
`scraped_at` duplicates `created_at`, and the archive records each version's fetch time.
`case_number` becomes NOT NULL; the live table has no nulls.
The dispatch times and response durations stay: they are parsed fields, and Connor plans reporting on them.

### `pdf_urls`

Adds `error_kind`, `content_hash`, `parser_version`, `extractor_version`, `parsed_count`, `stored_count`, `skipped_count`, `header_lines`.
Drops `raw_text` and `entry_count`.

### Provenance columns

One SQLAlchemy mixin adds these to both lookup tables.

| Column | Type | Notes |
|---|---|---|
| `source` | text | `rule`, `ai`, or `human`, with a check constraint. Null while a value waits. `rule` is used only for locations, by the rule pass. |
| `prompt_version` | text | The effective prompt version of the AI answer, or `rules-<RULES_VERSION>` for a rule row. Null for `human`. `--redo` uses it to skip rows already on the current version (7.14). |
| `ai_call_id` | text | The `ai_calls` document that produced the last AI answer. It stays when a human takes over the value. Its document holds the backend, model, and prompt version. |
| `needs_review` | boolean | The review mark. |
| `failed_attempts` | integer | Default 0. |

A row may exist with no normalized value: that is where failed attempts and the review mark live for a raw value AI has not answered.
Deleting the row hands the value back to AI and clears the count in one step (7.12).

### `incident_type_categories`

Adds `normalized_type` and the provenance columns.
`category` becomes nullable.
`subcategory` is dropped; the table is empty.

### `address_normalizations`

Adds `kind`, `place_code` (indexed), `street`, `geocode_query`, `geocode_attempts`, `coordinate_precision`, and the provenance columns.
Public location is not stored; the dbt models compute it.
The `geocoded_via` check widens to `manual`, `nominatim`, `place_code`.
`source` says who owns the row; `geocoded_via` says how its coordinates were found.

### `ai_calls` in MongoDB

One document per AI call, written best-effort through the archive's writer; its shape and indexes are in the raw source archive design.
It holds the field, the raw values sent, the prompt, the raw answer, the accepted items, the backend, model, prompt version, duration, and outcome.
A human edit overwrites the current value in Postgres, and the AI's answer stays in its call document (7.13).

### Migrations

Two: `log_entries` and `pdf_urls` columns; the lookup tables; nothing for the consumer models, which dbt owns.
Each lands with the pull request that uses it.

## Error handling

| Failure | What happens | Criteria |
|---|---|---|
| Download fails or times out | Errback marks `error` kind `download`; retried until 3 attempts. | 2.7, 2.10 |
| PDF yields no valid entries | `error` kind `parse`, waits for a reprocess of the archived original. | 2.8 |
| Parse or save error while the archive is down | `error` kind `download`, so it is downloaded and archived again. | 2.8 |
| Reprocess finds no archived version | URL record back to `pending`, counted. | 4.12 |
| Archive unreachable at reprocess start | Reprocess exits with an error before changing anything. | 4.13 |
| `ai_calls` cannot be written | Normalizations stored anyway; lost call records counted. | 8.14 |
| PDF unreadable | `error` kind `download`, retried until 3 attempts. | 2.7 |
| One entry invalid | Skipped and counted; the rest of the PDF is stored. | 2.4 |
| Transaction fails | Rollback, `error` kind `save`; other PDFs unaffected. | 2.3, 2.6 |
| Process dies mid-PDF | Claim expires after 120 minutes; the attempt was counted at claim. | 2.9 |
| AI call errors or times out | Nothing stored; values wait; no failed attempt counted. | 8.1, 8.6 |
| AI answer empty or off-schema | Nothing stored from that call. | 8.2 |
| AI item missing, duplicated, or invalid | Item dropped; that value gets a failed attempt; 3 gives a review mark. | 8.3, 8.4, 8.7 |
| AI says unsure | Stored with a review mark. | 8.5 |
| AI gives a street not on the street list | Stored with a review mark. | 6.22 |
| Street list empty (VGSI not scraped yet) | No location AI calls this run; an error is logged; the rule pass's place-code reuse still runs. | 6.23 |
| Backend logged out or at its usage limit | No more AI calls this run. | 8.9 |
| Every AI call fails | Job exits non-zero on the Mac; the daily DAG is unaffected. | 8.11, 16.4 |
| Geocoder miss or failure | Address kept, coordinates untouched, attempt counted. | 6.5, 6.6 |
| Coordinates outside the city bounds | Discarded. | 6.4 |
| A dbt test fails | Build fails and names the test and row count; the run shows failed. | 14.1, 14.6, 12.7 |

## Testing strategy

One mechanism for database tests, replacing the three that exist (`TEST_DATABASE_URL` in the migration test, `FakeSession` in the scrapers tests, mocked sessions in the API tests):

- `conftest.py` sets `POSTGRES_DB=app_test` before anything imports the client, and stops the run if the name does not end in `_test` (13.2).
  The check runs before any connection.
- MongoDB tests use the archive spec's plugin and the `scraped_data_test` database; ingest and reprocess tests need it, so CI starts `mongo` next to `postgres`.
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
- Canonical rules and the rule pass: pure-function tests over known spelling pairs, plus a job test showing that a house number on a listed street is stored as `rule` and that `FakeBackend` never sees it.
- No tools: the `ClaudeCliBackend` contract test checks, with a fake executable, that each call runs in a new empty directory and passes the flags task 13 settles (9.8).
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

### A workflow, not an agent

Code loads each batch, a rule pass settles exact matches, and the model gets only the leftovers and the street list.
The model has no tools and no database, and returns JSON against a schema.
Code parses it with Pydantic, checks it in `checks.py`, and upserts it, never over a `human` row.

Why:
- The steps are known in advance, so a fixed workflow is simpler, cheaper, and easier to test than an agent deciding its own steps.
  Anthropic's "Building effective agents" (https://www.anthropic.com/engineering/building-effective-agents) recommends workflows for well-defined tasks, and starting with the simplest solution.
- Every model input is scraped text from city PDFs that anyone could influence.
  A model with no tools has no way to act on an injected instruction: the worst it can do is a wrong answer, which the checks and the review mark catch.

Rejected alternatives:
- **An agent with MCP read and write tools, such as `get_pending` and `save`.**
  - It gives the model write access it doesn't need, which is OWASP LLM Top 10's Excessive Agency (LLM06).
  - It puts untrusted content, private data, and a way to act or send data out in one process. That is Simon Willison's lethal trifecta (https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/).
  - Retries and partial writes get messy: a session that dies after three saves out of fifty leaves the batch half done, and the next run has to work out which half.
  - It's hard to test, because the tests would have to script a tool-calling conversation, not compare one answer.
  - It needs an MCP server and headless tool permissions to run under Airflow.
- **A read-only `find_street` lookup tool. Deferred, not rejected.**
  This is the upgrade path if the street list in the prompt proves too big or too weak.
  The trigger is a measured list of more than about 1,500 streets, or evaluation misses that a lookup would fix.
  It needs a small MCP server, because `claude -p` runs with tools off here, and it would keep the job as the only writer.

### The AI normalizing runs by hand on Connor's Mac

The normalization job runs on the host, started by Connor, with his normal `claude` login.
The daily DAG has no normalize task.

- No long-lived token in `.env`.
  `claude setup-token` gives a one-year token that anyone who can read `.env` or the container environment could use against his Max plan.
- No Claude login inside a container.
  The Airflow image stays free of the CLI, its config, and its credentials, and the containers that read scraped text hold nothing that can call a model.
- He can run it by hand, watch the summary, and check the review list before anything reaches the public map.
  That fits a hobby project at this size: a few thousand distinct values, then a handful a day.
- Rejected: the `claude` CLI in the Airflow image with a `setup-token` token in `.env`.
  It's fully scheduled, but it puts a long-lived subscription credential in a file and in every Airflow container.
  The `airflow-claude-cli` branch holds that idea, unbuilt.
- Rejected: an interactive `claude` login inside the container.
  The login has to be redone by hand whenever the container or its volume is rebuilt, and it still leaves a credential in a container that reads scraped text.
- Cost of the choice: normalizing waits for Connor, so new values reach the map a day or two late, and only while he runs it.
  The DAG keeps working on raw values meanwhile (8.12, 11.9), and a LaunchAgent can take over later without a code change.

### Rules first, AI for the leftovers

- Exact matches, meaning a house number on a known street, two known streets, or a known place code, are settled by `shared/locations` rules, which are free, instant, and repeatable.
  Only what the rules can't settle uses Max plan usage.
- The street list comes from parcels because VGSI lists every addressed street in the city, and it's already scraped.
- Rejected: sending every location to AI.
  It spends calls on values a rule reads exactly, and two runs can disagree.
- Rejected: a second copy of the canonical rules in SQL for the address entity's dbt models.
  Two implementations would drift, and the address key depends on them matching.

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

### Human corrections win, and AI calls are logged in MongoDB

- Rejected: overwrite on conflict, as both old scripts do.
- Rejected: `ai_value` columns beside each normalized value.
  They keep only the latest AI answer, so a redo erases the one before it.
- Rejected: an append-only `ai_answers` table in Postgres.
  It holds raw, variable-shaped payloads that nothing joins; MongoDB keeps every call, failed ones too, and Postgres keeps one `ai_call_id`.

### Structured data in Postgres, raw source in MongoDB

Connor's rule: every parsed, structured field goes in Postgres, and raw, unparsed source goes in MongoDB, where nothing scraped is ever thrown away.
The original PDFs, each entry's raw and unsplit text, and the AI call records live in MongoDB; the parsed fields, counts, and times live in Postgres for the reporting Connor plans.

- Rejected: keeping the extracted PDF text in `pdf_urls`, which the reviewer and the PM recommended.
  It kept reprocess Postgres-only and independent of pypdf, and left the archive a pure side copy.
  Connor chose to move it, and the design pays for that with four rules:
  the archive is backed up before it ships;
  the extractor version is recorded and a pypdf bump counts as a parser change;
  parse and save errors become download errors when the archive did not store the PDF;
  reprocess sends a record with no archived original back to the download queue.
- Rejected: keeping each entry's block text in Postgres.
  It is raw source, the PDF text split up, and no query reads it; it lives on the archived version, keyed by case number.
- Rejected: dropping parsed fields nothing reads yet, such as the officer code, every "Refer To" reference, and the dispatch times.
  They are structured, and Connor plans reporting on them.

### `claude -p` with Haiku by default, Ollama opt-in, behind one interface

- Rejected: calling the CLI straight from the job.
  Tests would patch `subprocess`, and a second backend would mean a rewrite.
- Rejected: Ollama as the default.
  Docker on macOS gives containers no GPU, so a 50-item batch would likely take several minutes on CPU, and small models drop items and alter the strings they should echo.
  Those figures are estimates, which is why the evaluation command exists: the local model is used for a scheduled run only after its score is recorded.
- Rejected: any paid API.

### dbt builds the consumer models

The admin API, the Elasticsearch sync, and the public export disagreed about what an incident is because each wrote its own query, one of them in Rust.
dbt gives one definition in staged SQL models, with the data checks as tests beside them and lineage docs for free.

- Rejected: one plain Postgres view in an Alembic migration.
  It is one file and no new tool, and it would work.
  But changing a view means a migration, the data checks would need their own home, and three stacked views in migrations are hard to read.
  dbt is also a tool worth knowing and showing.
  dbt has two costs of its own: every migration run must drop and rebuild the views, and the marts mapping has to sit outside the ORM's metadata.
- Rejected: dbt tables instead of views.
  A correction would not show in the admin until the next build.
- Rejected: the same join written in each consumer, as today.

### Admin search in Postgres, not Elasticsearch

Incident search runs as a Postgres query over the dbt models, with full-text search for words and pg_trgm for typos.

- Rejected: keeping Elasticsearch for incidents.
  It needs a sync stage, a second copy of every incident, and a JVM service in the stack, for one admin user and under 100,000 rows.
  A correction would not show until the next sync, while the Postgres query sees it on the next request.
- Rejected: Postgres full-text search alone.
  It does not match typos in street names, the most common miss in police log locations, and its parser cannot match part of a case number.
- Rejected: pg_trgm similarity alone for typos.
  A wrong letter in the middle of a short word removes three trigrams, so "Mxple" scores 0.333 against "Maple".
  Edit distance says exactly what 10.6 promises, and trigrams stay as its prefilter.
- Rejected: a dedicated search table from the start.
  It would make search wait for the daily build.
  Per-table indexes are the first fallback if the timing test fails, and the search table the second.

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
   Settled on 2026-11-13: there's no token. The job runs by hand on Connor's Mac with his login (see Decisions).
4. **The officer column on the public site.**
   The export writes an empty `officer`, so the officer column and filter in `incidents-table.tsx` will have nothing to show until the frontend changes.
5. **Who labels the evaluation set.**
   The plan is an AI-drafted set that Connor checks line by line, about 150 lines.
6. **Cross-entity admin search.**
   Settled: `/api/search` moves to Postgres for all nine record types, under the search spec, in one pull request after PR 9 and before the Elasticsearch removal.
7. **The address entity's canonical rules.**
   The draft on `spec/address-entity` puts them in a dbt macro.
   They now live in `shared/locations/canonical.py`, so that spec has to read a stored canonical value, for example a `canonical_address` column written by this job and by the property pipeline, and not recompute it in SQL.
   This is decided when that spec's design is filled in.
8. **The street list's real size.**
   It's measured in task 14.
   Past about 1,500 streets, choose between trimming it (for example, to streets that appear in the logs) and the `find_street` tool.
