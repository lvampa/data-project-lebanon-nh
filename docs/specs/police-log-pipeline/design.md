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
4 export     report-gen ─► JSON in data/export (local dev; publishing is not built)
```

The `discover_urls` DAG runs weekly and triggers `process_urls`, which together are stages 1 and 2.
`police_log_reprocess` is a manually triggered DAG for stage 2.
Stage 3 runs by hand: `uv run normalize` and `uv run geocode` from the repo root.
Stage 4 is `scripts/generate_report.sh`, and the site's code deploys separately with `scripts/deploy.sh`, which CI runs; see the site deploy spec.
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
- **One spelling per crossing:** an intersection is stored with its two streets in alphabetical order, ignoring case, so "Poverty Ln and Mechanic St" and "Mechanic St and Poverty Ln" are one text and share a pin.
  Each street keeps its own spelling.
  A new spelling of a crossing that is already stored takes the stored text, a `human` row's first and then the lowest id, so "Lahaye" and "LaHaye" do not make two pins.
  This applies only to the `intersection` kind, since "Wright and Sons, Main St" is a place, and the geocode query for a crossing is rebuilt from the stored text.
  `RULES_VERSION` is 3 because a rule row for a crossing now reads in this order.
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
  Before calling Nominatim it reuses coordinates from another row with the same place code, kind and street, or the same normalized address and kind.
  A place code can name an area (code `E` covers a dozen streets), so a code alone is not enough, and a row with no street never takes a code's pin.
  `--retry-approximate` joins rows by a shared place code under the same rule.
  A hand-placed donor is used too, so two spellings of one address never land on different spots; the copy keeps its `source`, and `geocoded_via` says how the pin was found.
  Otherwise it tries the geocode query, then the newest OpenStreetMap snapshot, then the street alone (an `approximate` result).
  An intersection takes only a point, from the geocoder or the snapshot; a street point is a miss for one, since the middle of a street is not where it crosses another.
  From the snapshot, a house address is matched by number and street, and an intersection by a node its two roads share, both with no AI.
  A named place gets up to 8 real features that share a meaningful word with its name and lie within 200 m of its street, and the AI answers with one number or 0.
  The AI never gives coordinates, an out-of-range answer is a failed call, and the job makes at most 100 such calls a run.
  A match sets `geocoded_via = 'osm'`, `osm_ref` and precision `exact`.
  `--no-llm` skips the AI step.
  `--retry-approximate` looks again, from the snapshot only, at every `ai` or `rule` row on a street point, a group at a time (rows with one normalized address and kind, joined by a shared place code), and skips a group with a `human` row.
  A miss changes nothing but the mark below, and a row is re-read under a lock before it is written.
  `--retry-missed` does the same, from the snapshot only, for `ai` and `rule` rows with no point that are marked for review: a row that missed three times, and a bare highway that had no road.
  A hit places the group and resets its attempts, and leaves the review mark, since normalize sets that mark for unsure answers and off-list streets too.
  A miss changes nothing but the mark below.
  Both retries record in `snapshot_checked` what a row was looked up with, on a miss as well as a hit: the snapshot, the place-match prompt version, and the row's kind, street and normalized address.
  A group whose rows all carry the mark they would get now is skipped, so a run reaches the places never asked.
  A change to any of the five, from normalize or a script, is a new question, so nothing clears the mark.
  A miss is marked only when the lookup really answered no: not when there was no AI for a place with candidates, the call cap was reached, the backend stopped or a call failed.
  The retry summary's "skipped as already checked" count is the groups it did not look at for that reason, so a run that places nothing and skips many is done, not broken.
  The two retries cannot be used together.
  Every run that places anything from the snapshot writes `tmp/geocode-matches-<date>.csv` with the old and new coordinates side by side, so a batch can be reverted from the file.
  It runs at 1 request per second, stops at 600 requests, and discards a result outside the city: state New Hampshire, city Lebanon or West Lebanon, and a coarse bounding box.
  An approximate answer, a road with no point on it, is accepted only when the road it names is the road the row is on: its name equals the street's once spelled the same way, or its route number matches, as "ROUTE 120" matches a road with `ref` "NH 120".
  A search that cannot find a road can answer with another, and 283 highway rows on Interstate 89 were all once pinned on Hanover Street.
  The street is the row's `street`, or the street part of its normalized address with the house number dropped, and an answer with no name and no route is a miss.
  After 3 misses a row is marked for review.
  A transient failure (a timeout, a connection error or a 5xx) skips the row without charging an attempt, and the next run tries it again.
  A 403 or 429 stops the run at once, and so do 5 transient failures in a row.
  A bare highway, one with no cross street, exit or landmark, is not looked up on Nominatim.
  Before, it was only marked for review. It now gets an approximate point on the road the snapshot matches by name or route number, stored with `geocoded_via = 'osm'` and precision `approximate`, and is marked for review only when no road matches.
  "ROCK CUT - ROUTE 120" is bare too, and gets the same point as "ROUTE 120".
  A highway that names a point, with an exit, a mile marker or milepost, a rest area, "over" or "under" a road, a cross street, "near" or "at", is looked up on Nominatim and takes only an exact point, never a road point or a street point, as an intersection does.
  Every run prints the share of parsed log entries that sit on a pin, by the kind of their location, and the export prints the share of in-range entries that are on the map.
- **OpenStreetMap snapshot:** `uv run osm-snapshot` downloads every named or numbered feature and every named road inside Lebanon's own boundary (not a box, which takes in White River Junction, Vermont) in two Overpass requests, and writes `scripts/data/osm/snapshot-YYYY-MM-DD.json`, which is gitignored.
  Overpass answers 429 or 502 when busy, so a request is retried 4 times with waits of 10, 30, 90 and 180 seconds, then fails with the last status.
  The functions in `shared/locations/src/locations/osm.py` find a location in the newest snapshot with no network: a house address by number and street, an intersection by a node two named roads share, and a named place by candidates that share a meaningful word with the name and lie within 200 m of its street.
  Street names are compared through `canonical_address`, so OpenStreetMap's "Mount Support Road" and the log's "MT SUPPORT RD" are one street.
  The roads query also takes ways that have a `ref` and no name, which is how Interstate 89 is stored, and a road keeps its `ref` as `route_ref`.
  A snapshot saved before that still loads, with no route numbers.
  The log names a highway by its number, so a road also matches by route: "ROUTE 120", "RT 120", "NH 120" and "STATE ROUTE 120" are NH 120, "INTERSTATE 89" and "I-89" are I 89, "US 4" is US 4, and a bare "ROUTE 4" is NH 4 or US 4, never an interstate.
  A way's routes are its `ref` values, split on a semicolon, plus the one its name spells out.
  A bare "ROUTE N" that finds both an NH N road and a US N road, which are not the same way, is a miss, and the number is matched with its letter, so 4 never matches 4A.
  A point on a road is halfway along its longest way, measured in meters over the part inside the city, since Overpass returns whole ways and Interstate 89 runs out of town. It is approximate, and a way wholly out of town has no point.
- **Placing by hand in bulk:** `uv run place-sheet export` writes a CSV of the places and house addresses still on a street point, busiest first, with the calls the map counts for them (every call but road traffic), a link to OpenStreetMap, and empty `lat` and `lng` columns.
  `uv run place-sheet import` reads it back under the `geocode` lock.
  A filled row sets every `ai` or `rule` row for that address, if it still sits on the sheet's point, to `source = 'human'`, `geocoded_via = 'manual'` and precision `exact`, the same fields the admin API writes for typed coordinates.
  A blank row is skipped, and a bad number or a point outside Lebanon is rejected with its line number.
  The sheet has an optional `source_url` column.
  A filled row with a `source_url`, which must be an http or https link, is written as `geocoded_via = 'research'` instead: precision `exact`, `geocode_source_url` set, `osm_ref` cleared, and `source` left as `ai` or `rule`, since a person did not check the spot.
  A research pin is exact, so `--retry-approximate` skips it and no lookup replaces it, and another spelling of the address copies it with its link.
  A person's correction through the admin API clears `geocode_source_url` and `osm_ref` along with the old pin.
  In both CSV files, text that starts with =, +, - or @ is quoted, and the import undoes the quote.
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
