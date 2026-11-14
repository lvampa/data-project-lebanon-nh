# Police log pipeline: tasks

**Status:** In progress
**Created:** 2026-11-06
**Updated:** 2026-11-07

The work stacks on the `fix/*` pull requests: PR 1 branches from the last of them, `pr/url-queue`, and each later one from the one before.
It ships as nine pull requests of 10 to 40 files each, with archive PR 1a before PR 2, and archive PRs 1b and 1c before PR 2b, because PR 2 stops storing PDF text in Postgres.
Then the search spec's Postgres pull request moves `/api/search` off Elasticsearch, and one follow-up here removes Elasticsearch.
Each one leaves the pipeline working and is tested against `app_test` before it is pushed.
File counts are estimates and include tests.

| PR | What ships | Files |
|---|---|---|
| 1 | Test harness, ported tests, migrations by hand | about 15 |
| Archive 1a | Raw source archive: test harness, archive class, middleware (archive spec) | about 20 |
| Archive 1b | Raw source archive: reads, AI call log, LLC and budget sources, parcel replay (archive spec) | about 16 |
| Archive 1c | Raw source archive: backup and check command (archive spec) | about 10 |
| 2 | Entry schema, one ingest function, process job, entry texts to the archive | about 32 |
| 2b | Move the raw text columns to the archive: legacy copy, guarded drop | about 18 |
| 3 | Parser fixes, reprocess from the archive, operator commands | about 22 |
| 4 | Normalization records, locations package, correction API | about 34 |
| 5 | AI normalization job and geocode job | about 24 |
| 6 | Evaluation set and the Ollama backend | about 12 |
| 7 | dbt consumer models and data checks | about 22 |
| 8 | API, admin search, and export read the models | about 14 |
| 9 | Daily schedule and the Airflow image | about 10 |
| Search | `/api/search` on Postgres, in the search spec | about 12 |
| Follow-up | Remove Elasticsearch | about 25 |

## Already met by the fix branches

These criteria need no task here.
QA still checks them in task 24.

- [x] 2.1 One URL record per canonical URL (`pdf_urls` unique constraint).
- [x] 2.2, 2.3 Entries and `complete` in one transaction, `error` on failure.
- [x] 2.6 One PDF's failure does not lose another.
- [x] 2.9, 2.10 Claim lease of 120 minutes, attempts counted at claim, stop at 3.
- [x] 6.12 A failed geocode on PATCH keeps the coordinates.
- [x] 12.4 One run at a time, for the existing DAGs.

## PR 1: Test harness, ported tests, migrations by hand

About 15 files.
No behavior change.
The three spec files ride along in this pull request.

- [x] 1. Add the real-database test harness
  - A pytest plugin in `shared/postgres`: set `POSTGRES_DB=app_test`, stop if the name does not end in `_test`, create the database if missing, and run the migrations.
  - For each test, rebind the existing sessionmaker to one connection with savepoints and restore it after. No production code changes.
  - Move the migration test onto the plugin, keeping its rolled-back Alembic connection.
  - Note in the README that tests and the pre-push hook need Postgres running.
  - _Requirements: 13.1, 13.2, 13.3, 13.4_

- [x] 2. Port the fake-session tests to the real database and add the missing cases
  - Port: complete only with its entries, a failed PDF does not lose an earlier one, error on a failed transaction.
  - Add: the same case number twice gives one row, two claims of one URL record give one winner.
  - Delete `FakeSession`.
  - _Requirements: 13.6_

- [x] 3. Document running migrations by hand
  - A README section with the one command, `uv run migrate`, run from the repo root against the compose Postgres. It runs `alembic upgrade head`, then creates the MongoDB indexes. No compose service runs it.
  - The test harness still migrates its own test database to head; that is separate.
  - _Requirements: 12.8_

## PR 2: Entry schema, one ingest function, process job

About 32 files.
It builds on archive PR 1a and drops nothing, so it needs no gate.
This is the pull request that changes how entries are written, so it ships alone; the column drop follows in PR 2b.

- [x] 4. Add the `log_entries` and `pdf_urls` columns
  - One Alembic migration with the columns in design.md, `case_number` and `log_date` NOT NULL, `created_at` from `scraped_at`.
  - Backfill `log_date` from the URL record, else from `reported_at`, and fail the migration if any row is still null.
  - Keep adding `officer_code`, `refer_to`, and the entry `parser_version`; the raw text columns are dropped in PR 2b.
  - Add `pdf_urls.content_hash`, `parser_version`, and `extractor_version`.
  - Update the ORM models and `PoliceLogRecord` (`extra="forbid"`, required `case_number` and `log_date`).
  - _Requirements: 1.3, 1.4, 1.5, 1.6, 1.7, 2.13_

- [x] 5. Add `ingest_log_text`
  - Parse, validate, and upsert one PDF's entries from `model_dump()`, guarded so unchanged rows are not touched and the later log date wins.
  - Count parsed, inserted, updated, unchanged, skipped, missing, and header lines; set and clear `missing_from_parse`.
  - Tests: the upsert, a skipped invalid entry, an entry with no case number, the later-date rule with the older PDF second, an entry stored before this pull request is updated by a fresh ingest, and a second call that changes no row.
  - _Requirements: 1.1, 1.4, 2.4, 2.5, 2.12, 2.13, 2.14, 13.6_

- [x] 6. Move the process job onto `ingest_log_text`
  - `PoliceLogPdfItem` carries the text and the content hash, not parsed entries; delete `PoliceLogItem` and its test.
  - Add `error_kind`; retry only `download` errors; a PDF with no valid entries is kind `parse`, an unreadable PDF kind `download`.
  - When `response.meta["archived"]` is false, parse and save errors are kind `download` instead; test it with a failing archive write.
  - After commit, write one `police_log_entry_text` version per entry, best-effort.
  - Add the runner that exits non-zero when a record moved to `error`, and the advisory lock.
  - Point the `process_urls` DAG spec at the runner.
  - _Requirements: 1.4, 2.7, 2.8, 2.15, 4.11_

## PR 2b: Move the raw text columns to the archive

About 18 files.
It does not ship until the gate in the raw source archive's tasks.md holds.

- [x] 6b. Copy and drop the raw text columns
  - `maintenance.archive_raw_text`: copy every `pdf_urls.raw_text` and every Mongo `urls` stored text to `police_log_text`, and every `log_entries` row's `raw_text` and `raw_reason_action` to `police_log_entry_text`, with the counts, a non-zero exit when one falls short, and a second run that changes nothing.
  - The migration that drops `pdf_urls.raw_text`, `log_entries.raw_text`, `raw_reason_action`, and `scraped_at`, stopping before any drop when a value is not archived. The downgrade re-adds the columns, empty.
  - Drop `raw_text` from the incident document in `scripts/sync/sync_es.py`.
  - Tests: the copy, its counts, the second run, and the migration refusing to drop when a value is missing.
  - _Requirements: 1.4, 1.6; raw source archive 8.4 to 8.8, 8.12_

## PR 3: Parser fixes, reprocess from the archive, operator commands

About 22 files.

- [ ] 7. Fix the parser
  - Bump `PARSER_VERSION`, record `EXTRACTOR_VERSION`, and add the pypdf comment in `scrapers/pyproject.toml`.
  - Parse "Vicinity of:" locations, the "Call Source:" line, every "Refer To" kind, the place code, and the officer code.
  - When no disposition matches, keep the unsplit text as the raw incident type.
  - Move the disposition list to its own module, add every disposition found in the stored PDFs, and set `disposition_unmatched` when none matches.
  - One text fixture and test per gap, cut from the stored PDFs.
  - Document that changing the disposition list means a parser version bump and a reprocess.
  - _Requirements: 1.3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8_

- [ ] 8. Add the reprocess script
  - `reprocess_police_logs.py --from --to | --all`, in log date order, over `complete` and `error` records, reading the newest archived version and extracting with pypdf.
  - Mark repaired `error` records `complete`, record the content hash and versions, log the counts, take the advisory lock.
  - A record with no archived version goes back to `pending`; an unreachable archive stops the run before any change.
  - Tests against `app_test` and `scraped_data_test`: no download, no normalization changed, a second run changes no row, a parser version bump alone does not move `updated_at`, a missing original is requeued.
  - A manual `police_log_reprocess` DAG spec.
  - _Requirements: 3.3, 4.1 to 4.13_

- [ ] 9. Add the operator CLI
  - `errors`, `reset <url>...`, and `unmatched-dispositions`.
  - _Requirements: 2.11, 3.7_

The 343 entries stored before this work are not repaired by reprocess, because their PDFs were never archived.
They are repaired when discovery adds their three PDFs again and the process job downloads and archives them.

## PR 4: Normalization records, locations package, correction API

About 34 files.
If it passes 40, the `shared/locations` package (task 11) ships first as its own pull request.
No AI yet.

- [ ] 10. Add provenance to the lookup tables
  - One mixin with `source`, `ai_call_id`, `needs_review`, and `failed_attempts`; `normalized_type` in place of `subcategory`; the location columns in design.md, with no stored public location; the widened `geocoded_via` check.
  - One Alembic migration, covered by the up and down test.
  - Delete the three old categorizer scripts and their tests, which stop working when `subcategory` goes.
  - _Requirements: 6.1, 6.9, 7.1, 7.2, 7.10_

- [ ] 11. Add the `shared/locations` package
  - Move `geocode_nominatim` out of `api/`, with the city-bounds check, the 1 per second limiter, and exact or approximate results.
  - Add the package to both Dockerfiles.
  - _Requirements: 6.4, 6.7, 6.9_

- [ ] 12. Extend the categories and addresses services and routes
  - Paged lists with source, review mark, and has-normalization filters, and entry counts.
  - PATCH sets `source = 'human'`, clears the review mark, rejects a category outside the five with 422, accepts coordinates outside the city bounds.
  - DELETE hands a value back to AI.
  - Real-database API tests, including a raw value with a slash and an apostrophe.
  - _Requirements: 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.12_

## PR 5: AI normalization job and geocode job

About 24 files.

- [ ] 13. Add the AI backend interface
  - `AiBackend`, `FakeBackend`, and `ClaudeCliBackend` with structured output, the configured model, the timeout, and the API key check.
  - Contract tests: valid, empty, malformed, timeout, login failure.
  - Confirm the CLI flags against `claude --help`, and capture real output for the login and usage-limit cases.
  - _Requirements: 8.1, 8.2, 8.9, 9.1, 9.2, 9.3, 9.4, 9.7, 13.5_

- [ ] 14. Add the prompts, answer models, and checks
  - Prompts and versions for both fields, as in design.md.
  - Pydantic answer models reusing `IncidentCategory`; `checks.py` for not sent, sent twice, missing, abbreviations, and name reuse.
  - The dispatch abbreviation list.
  - _Requirements: 5.2, 5.5, 5.6, 5.7, 8.3, 8.4, 8.5_

- [ ] 15. Add the normalization job
  - Waiting values, case and spacing groups, batches of 50, 5 calls per field with spillover, per-value failed attempts, the review mark at 3.
  - Writes never touch `human` rows; `--redo` keeps the old value until a valid new one arrives; every call, failed or not, goes to `ai_calls` in MongoDB, best-effort.
  - The per-field summary log and the exit code.
  - Tests with `FakeBackend` for every AI row in design.md's error table.
  - Each accepted item stores its call's `ai_call_id`; a test with MongoDB unreachable stores the normalizations and counts the lost call records.
  - _Requirements: 1.2, 5.1, 5.3, 5.4, 6.1, 7.2, 7.9, 7.11, 7.13, 8.6, 8.7, 8.8, 8.10, 8.11, 8.13, 8.14, 9.5, 9.6_

- [ ] 16. Add the geocode job
  - Place-code reuse, query then street fallback, the bounds check, 3 attempts, 600 requests per run, no bare highways, no `human` rows.
  - Tests with a fake geocoder.
  - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6, 6.8, 6.10_

## PR 6: Evaluation set and the Ollama backend

About 12 files.
This one waits on Connor checking about 150 labeled lines.

- [ ] 17. Add the evaluation set and command
  - Two JSONL files of at least 50 lines each, drafted from the stored PDFs with a different model and prompt than the one scored, then checked by Connor.
  - A fixed list of type names in use, stored with the set, so the command never reads the database.
  - `normalize.evaluate` with accuracy per field, discarded and unsure counts, and the list of wrong items.
  - Record the first `claude -p` run in `eval/results.md`.
  - Unit tests for the scoring with a fake backend.
  - _Requirements: 15.1 to 15.7_

- [ ] 18. Add `OllamaBackend` as an opt-in
  - The backend, its contract test fixture, and a compose profile that is off by default.
  - Record its evaluation score in `eval/results.md`.
  - _Requirements: 9.1, 9.3, 15.8_

## PR 7: dbt consumer models and data checks

About 22 files.
Nothing reads the models yet, so this ships alone.

- [ ] 19. Add the dbt project and data checks
  - First step: confirm dbt-postgres resolves in the workspace's single `uv.lock`. If it does not, `transform/` becomes its own project outside the workspace.
  - `transform/` with the staging and marts models in design.md, built as views in a `marts` schema.
  - The dbt tests in design.md, with the disposition seed generated from the parser's list before each build.
  - The `public_location` macro, including the under-100 rule, used by the public models.
  - Change the `migrate` service in `compose.yml` from PR 1, and add a separate test fixture, so both drop `marts`, run the migrations, then `dbt run`.
  - Tests: a passing build on good rows, one bad row per check that fails it, and a migration that drops a column a model uses still upgrades.
  - _Requirements: 6.11, 8.12, 10.13, 11.1, 11.2, 11.6, 11.7, 14.1 to 14.6_

## PR 8: API, admin search, and export read the models

About 14 files.

- [ ] 20. Read the models in the admin API and add admin search
  - Map `marts.incidents` on its own metadata, outside `Base`, and add its `search_text` column in dbt.
  - Incidents API returns raw and normalized values and filters by category, type name, and normalized address; stats count by category and type name.
  - First step: the seeded timing test, 100,000 incidents and a five-word query that needs the edit-distance path, under 1 second.
    Its fuzzy word is a 5-letter word with a wrong middle letter, such as "Mxple", the lowest-scoring typo, so the prefilter lets the most rows through and the test measures the worst case.
    If it fails, stop and choose a fallback from design.md before building the rest.
    The pre-push hook skips it; QA runs it.
  - Put the word matching in `api/services/text_search.py`, so the search spec can reuse it.
  - Add `q` to `GET /api/incidents`: every word must match by full text, by one edit for words of 5 or more letters behind a trigram prefilter of `>= 0.3`, or by case number for words of at least 4 digits and hyphens; ranked, then newest first.
  - One Alembic migration that enables `pg_trgm` and `fuzzystrmatch`.
  - Tests: every word must match; "Hanovr", "Hanpver", "Mxple", and "Maxle" find "Hanover" and "Maple"; "hannafords" finds "HANNAFORD'S"; "13339" finds "26-13339"; "St", "Main", "26", and "Mapel" do not fuzzy-match; a normalized address finds every raw spelling; a saved correction shows on the next request; parse errors are left out.
  - _Requirements: 10.1 to 10.13_

- [ ] 21. Read the public models in `report-gen`
  - Plain selects from the three public models; remove the joins and the 2,000 row cap.
  - Keep today's field names and the `addresses.json` shape; write the new fields.
  - The export keeps running from `deploy.sh` at deploy time; its files are not committed.
  - _Requirements: 11.3 to 11.12, 12.9_

## PR 9: Daily schedule and the Airflow image

About 10 files.

- [ ] 22. Add the daily `police_log` DAG
  - A plain DAG file next to `dags/specs.py`: discover, process with a limit of 100, normalize, geocode, then dbt build, with the failure rules in design.md and a final watcher task.
  - A 60 minute timeout per task and a pool of size 1 shared with reprocess.
  - Remove the `discover_urls` and `process_urls` specs.
  - Structure tests.
  - _Requirements: 12.1 to 12.7_

- [ ] 23. Make the AI call run in the Airflow image
  - Install the `claude` CLI and pass the token from `.env`; add a blank entry to `.env.example`.
  - Checked by hand when Connor builds the image: one real AI call from inside the container.
  - _Requirements: 9.1, 9.7, 12.2_

## Follow-up: Remove Elasticsearch

About 25 files.
It runs after the search spec's Postgres pull request, once nothing reads Elasticsearch, and does not touch the open `fix/*` pull requests.

- [ ] 24. Remove Elasticsearch from the stack
  - Remove what `pr/elasticsearch` (#3) adds, once it has merged.
  - `compose.yml`: the `elasticsearch` and `kibana` services, their volume, and the dependency on them and `ELASTICSEARCH_HOST` in both the Airflow services and the `api` service.
  - `.env.example`: `ELASTICSEARCH_HOST`.
  - DAGs: the `sync_elasticsearch` spec from `pr/dags`, the triggers that start it, the comment in `dags/build_dags.py`, and `test_every_indexed_source_leads_to_elasticsearch_sync` in `dags/tests/test_specs.py`.
  - Scripts: `scripts/sync/sync_es.py` and its test.
  - Dependencies: `elasticsearch` in the root `pyproject.toml` dev group, `scripts/pyproject.toml`, and anywhere else it is listed; update `uv.lock`.
  - API: the client in the `api/main.py` lifespan, `get_es` in `api/deps.py`, `elasticsearch_host` in `api/config.py` and `api/tests/test_config.py`, and the Elasticsearch ping in `api/routers/health.py` and `api/tests/test_health.py`.
    Change the health check in the same commit as the compose change, or `/healthz` returns 503 once the service is gone.
  - `/api/search` is already on Postgres by then; check that its tests and the preflight in `api/tests/test_cors.py` no longer need Elasticsearch.
  - The admin search page keeps working, because the response contract does not change.
  - Docs: `AGENTS.md`, the README, the search spec's status, and the Elasticsearch mentions in `docs/specs/city-budgets/design.md` and `docs/specs/planning-board/design.md`.
  - Check: the suites pass, `docker compose config` shows no Elasticsearch, `/healthz` returns 200 without it, and `grep -ri elasticsearch` finds only history in specs.

## QA

- [ ] 25. Test each pull request before it is pushed
  - Run the suites.
  - Do a real run of what the pull request adds against `app_test`, never `app`.
  - For PR 5, one real AI batch of 10 values; for PR 6, one evaluation run.
  - Report pass or fail for each criterion the pull request cites, and for the already-met criteria once in PR 1.
