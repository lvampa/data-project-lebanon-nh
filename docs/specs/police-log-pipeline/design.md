# Police log pipeline: design

**Status:** In progress
**Created:** 2026-11-06
**Updated:** 2026-11-14

## Overview

The pipeline turns the Lebanon Police Department's daily dispatch log PDFs into clean, mappable records.
It has four stages: collect, parse, normalize and geocode, and export and deploy.
Postgres holds every parsed, structured field.
MongoDB holds raw, unparsed source: the original PDFs, each entry's raw text, and the AI call records.
Normalized values sit in two lookup tables, keyed by the raw value, so each distinct spelling is cleaned once, not once per entry.

## Data flow

```
1 collect    city page ─► discover_urls ─► pdf_urls (pending)
                 process_urls: claim, download, extract text ─► archive middleware ─► MongoDB raw_sources (PDF bytes)
2 parse      PoliceLogPdfItem ─► ingest_pdf_url() ─► log_entries (raw parsed values)
             reprocess: archived PDF ─► pypdf ─► ingest_pdf_url()       (no download)
3 normalize  uv run normalize ─► rule pass, then AI for the leftovers ─► incident_type_categories, address_normalizations
  and        uv run geocode ─► Nominatim ─► coordinates on address_normalizations
  geocode    admin API edits ─► same tables, source = human (no job overwrites them)
4 export     report-gen ─► JSON in frontend/web/public/data ─► bun run build ─► wrangler pages deploy
```

The `discover_urls` DAG runs weekly and triggers `process_urls`, which together are stages 1 and 2.
`police_log_reprocess` is a manually triggered DAG for stage 2.
Stage 3 runs by hand: `uv run normalize` and `uv run geocode` from the repo root.
Stage 4 is `scripts/deploy.sh`.
`uv run migrate` applies the Alembic migrations and creates the MongoDB indexes, and backups are hand-run scripts.
There is no Elasticsearch and no dbt.

## Stages 1 and 2: collect and parse

- **Queue:** the Postgres `pdf_urls` table; see the PDF URL queue spec.
  A failed URL records an `error_kind`: `download`, `parse` or `save`.
  Only `download` errors are retried under the attempt limit.
  A parse or save error waits for a reprocess of the archived original.
- **Process job:** the spider downloads and extracts text.
  The archive middleware stores the PDF bytes in MongoDB first and tells the pipeline whether it worked.
  If it did not, a parse or save error becomes a `download` error, so the PDF is fetched and archived again.
  `run_process_urls.py` starts the crawl, holds the `police_log_parse` advisory lock, and exits non-zero if any URL moved to `error`.
- **One ingest function:** `ingest_pdf_url` in `scrapers/ingest/police_log.py` wraps `ingest_log_text`, the only place that parses and writes entries.
  The process job and the reprocess job both call it.
  Entries are validated with `PoliceLogRecord`, then upserted on `case_number`.
  An update applies only when a parsed column differs and the PDF's log date is not older than the stored row's.
  Entries stored for a source URL that are missing from a new parse are flagged `missing_from_parse`.
- **Parser** (`scrapers/parsers/`): a pure function with `PARSER_VERSION` and `EXTRACTOR_VERSION` (the pypdf version).
  A pypdf upgrade counts as a parser change.
  Disposition endings come from a list in `dispositions.py`; an entry whose ending is not on the list keeps its unsplit text and is flagged `disposition_unmatched`.
  Changing parser behavior or the list means bumping `PARSER_VERSION` and reprocessing.
  Parser fixtures are cut from real city PDFs.
- **Reprocess:** `scrapers/maintenance/reprocess_police_logs.py` re-extracts text from the newest archived PDF and re-ingests it.
  A record with no archived original goes back to `pending`.
  It takes the same `police_log_parse` advisory lock as the process runner, so an old parse never overwrites a new one.

## Stage 3: normalize and geocode

- **Rows:** `incident_type_categories` and `address_normalizations`, one row per distinct raw value.
  Each carries `source` (`rule`, `ai` or `human`), `prompt_version`, `ai_call_id` and `needs_review`.
  Addresses also carry a kind (`address`, `intersection`, `place`, `highway`), a place code, a street, a geocode query, coordinates and how they were found.
- **Workflow, not an agent:** code loads the batch, fixed rules settle exact matches, and the model sees only the leftovers.
  The model has no tools and no database, and returns JSON against a schema.
  Code validates it with Pydantic, checks it in `checks.py`, and writes it.
  A write never overwrites a `human` row.
- **Grouping:** values are grouped by a key (incident types by case and spacing, addresses by the canonical form from `shared/locations`).
  A new spelling whose key already has a normalization copies it with no AI call.
- **Rule pass for addresses:** a house number on a street from the street list, two listed streets joined by `and`, `&` or `/`, or a known place code is settled with `source = 'rule'`.
  The street list is built each run from parcel locations.
  Anything else goes to AI.
- **AI backend:** one interface, `AiBackend`.
  `ClaudeCliBackend` runs `claude -p` with every tool, setting, hook and MCP server turned off, from an empty temporary directory, and refuses to run if `ANTHROPIC_API_KEY` is set.
  The default model is Haiku.
  `OllamaBackend` is opt-in.
  A run makes at most 5 calls per field, of up to 50 values each.
  An item the model is unsure about, or a street not on the list, is stored with `needs_review`.
- **Failure handling:** a call that fails or returns a bad item costs that value a failed attempt, and a value gets 3.
  A login or usage-limit error stops the run.
  The job prints a summary, and it takes the `normalize` lock so two runs never spend the same AI calls.
  The geocode job takes its own `geocode` lock, so two runs never double the Nominatim rate.
- **Geocode job:** it takes `ai` and `rule` addresses with a normalized address and no coordinates, and never a `human` row.
  Before calling Nominatim it reuses coordinates from another row with the same place code, or the same normalized address and kind.
  A hand-placed donor is used too, so two spellings of one address never land on different spots; the copy keeps its `source`, and `geocoded_via` says how the pin was found.
  Otherwise it tries the geocode query, then the street alone (an `approximate` result).
  It runs at 1 request per second, stops at 600 requests, and discards a result outside the city: state New Hampshire, city Lebanon or West Lebanon, and a coarse bounding box.
  After 3 misses a row is marked for review.
  A transient failure (a timeout, a connection error or a 5xx) skips the row without charging an attempt, and the next run tries it again.
  A 403 or 429 stops the run at once, and so do 5 transient failures in a row.
  A bare highway with no cross street, exit or landmark is marked for review and never looked up.
- **Admin API:** `api/services/categories.py` and `addresses.py` list rows and let the operator correct them.
  A correction sets `source = 'human'` and clears the review mark; typed coordinates get `geocoded_via = 'manual'`.
  Deleting a row hands the value back to AI.
- **Locations package:** `shared/locations` holds the canonical address rules (pure, versioned by `RULES_VERSION`) and the Nominatim client.

## Stage 4: export and deploy

`report-gen` reads Postgres and writes the static JSON the frontend builds from; see the report generator spec.
The map joins `log_entries` to `address_normalizations` on the raw location.
The export ships unfiltered: exact addresses, officer names and the row cap as they are.

## Retention and what is not built

All history is stored, and nothing is expired or deleted.
The public site will show only the last year, and the admin shows everything.
The one-year window belongs in the export query, and it is not built yet: the export does not filter by date.

Not built yet:

- A single daily `police_log` DAG that runs collect, parse, normalize and geocode in order.
  Normalize and geocode are run by hand until then.
- The one-year export window.

## AI answer shape

The model returns JSON with one item per raw value it was sent.
Every item echoes the raw value and says whether the model is unsure.
Code rejects an item whose `raw` was never sent.

```
incident types   {"items": [{"raw": str, "unsure": bool, "category": IncidentCategory, "normalized_type": str}]}
locations        {"items": [{"raw": str, "unsure": bool, "kind": "address" | "intersection" | "place" | "highway",
                             "normalized_address": str, "geocode_query": str, "street": str}]}
```

`street` is a street from the street list, or an empty string when none fits.
The models are in `scripts/normalize/prompts.py`.

## Testing

Tests run against a real Postgres database, never a mock.

- The database name must end in `_test`.
  The pytest plugin in `shared/postgres` checks it before any connection and exits otherwise, so a test run cannot touch the live `app` database.
- Each test runs inside one transaction that is rolled back afterward.
  `SessionLocal` is rebound to that connection, so a commit in the code under test only releases a savepoint.
- Outside that fixture `SessionLocal` has no database, so a test that forgets it fails instead of committing rows for good.
- If Postgres is down, the tests fail with a message that says so.
  They do not skip.

## Data model notes

- `log_entries` keeps parsed raw values and is never rewritten by normalization.
- Normalized values live only in the two lookup tables.
- Every AI call is one `ai_calls` document in MongoDB (prompt, raw answer, accepted items, model, prompt version, outcome).
  Postgres keeps the document's ID, and writes the row without one if the document could not be saved.

## Decisions

- **Rules where the vocabulary is closed, AI where it is open.**
  Dispositions are a closed set that a list reads exactly and for free.
  Incident types have no fixed list, and addresses need judgment on the leftovers.
  Rejected: AI splitting type from disposition, which would be a second source of dispositions.
  Rejected: rules for incident types, which would need constant upkeep.
- **A workflow, not an agent.**
  The steps are known in advance, so a fixed workflow is simpler, cheaper and easier to test.
  Every model input is scraped text that anyone could influence, so a model with no tools can do no worse than give a wrong answer, which the checks catch.
  Rejected: an agent with read and write tools, which gives the model write access it does not need and makes retries and partial writes messy.
  Deferred: a read-only street lookup tool, if the street list in the prompt proves too big.
- **Normalizing runs by hand on the operator's machine.**
  It uses the operator's own `claude` login.
  Rejected: a long-lived token in `.env`, or a login inside the Airflow container, because both would put a subscription credential next to containers that read scraped text.
  The cost is that new values reach the map a day or two late.
- **Normalize distinct values, not entries.**
  Many entries repeat the same incident type or address, so distinct values are far fewer than entries.
  Rejected: normalized columns on `log_entries`, which would spend a call per entry and fan every correction out.
- **Two lookup tables, not one generic table or a places table.**
  The payloads differ, and a `place_code` column covers reuse of coordinates at a fraction of the size.
- **One ingest function for process and reprocess.**
  Rejected: a reprocess spider, because two code paths would drift and nothing needs downloading.
- **Answers are checked in code, never trusted.**
  Rejected: storing a batch without set checks, because an echoed value that was never sent would create a normalization for a string that does not exist.
- **Human corrections win.**
  Rejected: overwrite on conflict, and `ai_value` columns that keep only the latest AI answer.
- **Structured data in Postgres, raw source in MongoDB.**
  Rejected: keeping extracted PDF text in `pdf_urls`, which would keep reprocessing Postgres-only but leave the archive a side copy.
  The cost is paid by hand-run backups and by recording the extractor version.
- **`claude -p` with Haiku by default, Ollama opt-in.**
  Rejected: Ollama as the default, since Docker on macOS gives containers no GPU and small models drop items.
  Rejected: any paid API.
- **Tests run against a real database.**
  Rejected: fake sessions, which let a lost-rows bug pass.
- **A public filtering layer was built and parked.**
  It had dbt models for incidents, block-level addresses, held-back fields, a 90-day window and pre-deploy privacy checks, plus an export from those models.
  The source data is already public, and the layer cost more review time than it protects against.
  Draft PRs #41 and #42 hold the work, and the export ships unfiltered.
  Revisit if the site ever publishes more than the city's own logs already do.

## Open questions

- Do 2025 PDFs use the same layout?
  The parser is proven on three November 2026 logs, and the header-line count check will show any difference during a backfill.
- How does the CLI word a usage-limit failure?
  The backend matches a best-guess set of phrases until a real limit is hit.
- Who labels an evaluation set for comparing backends and prompts, if one is built?
