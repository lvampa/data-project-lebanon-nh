# Police log pipeline: tasks

**Status:** Draft
**Created:** 2026-11-06
**Updated:** 2026-11-06

The work stacks on the `fix/*` pull requests: PR 1 branches from the last of them, `pr/url-queue`, and each later one from the one before.
It ships as nine pull requests of 10 to 40 files each.
Each one leaves the pipeline working and is tested against `app_test` before it is pushed.
File counts are estimates and include tests.

| PR | What ships | Files |
|---|---|---|
| 1 | Test harness, ported tests, migrations at startup | about 15 |
| 2 | Entry schema, one ingest function, process job | about 20 |
| 3 | Parser fixes, reprocess, operator commands | about 20 |
| 4 | Normalization records, locations package, correction API | about 34 |
| 5 | AI normalization job and geocode job | about 24 |
| 6 | Evaluation set and the Ollama backend | about 12 |
| 7 | dbt consumer models and data checks | about 22 |
| 8 | API, search sync, and export read the models | about 14 |
| 9 | Daily schedule and the Airflow image | about 10 |

## Already met by the fix branches

These criteria need no task here.
QA still checks them in task 24.

- [x] 2.1 One URL record per canonical URL (`pdf_urls` unique constraint).
- [x] 2.2, 2.3 Entries and `complete` in one transaction, `error` on failure.
- [x] 2.6 One PDF's failure does not lose another.
- [x] 2.9, 2.10 Claim lease of 120 minutes, attempts counted at claim, stop at 3.
- [x] 6.12 A failed geocode on PATCH keeps the coordinates.
- [x] 12.4 One run at a time, for the existing DAGs.

## PR 1: Test harness, ported tests, migrations at startup

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

- [x] 3. Run migrations at startup
  - A one-shot `migrate` service in compose that the Airflow services wait for.
  - _Requirements: 12.8_

## PR 2: Entry schema, one ingest function, process job

About 20 files.
This is the pull request that changes how entries are written, so it ships alone.

- [ ] 4. Add the `log_entries` and `pdf_urls` columns
  - One Alembic migration with the columns in design.md, `case_number` and `log_date` NOT NULL, `created_at` from `scraped_at`.
  - Backfill `log_date` from the URL record, else from `reported_at`, and fail the migration if any row is still null.
  - Update the ORM models and `PoliceLogRecord` (`extra="forbid"`, required `raw_text`, `case_number`, `log_date`).
  - _Requirements: 1.5, 1.6, 2.13_

- [ ] 5. Add `ingest_log_text`
  - Parse, validate, and upsert one PDF's entries from `model_dump()`, guarded so unchanged rows are not touched and the later log date wins.
  - Count parsed, inserted, updated, unchanged, skipped, missing, and header lines; set and clear `missing_from_parse`.
  - Tests: the upsert, a skipped invalid entry, an entry with no case number, the later-date rule with the older PDF second, an entry stored before this pull request is updated by a fresh ingest, and a second call that changes no row.
  - _Requirements: 1.1, 1.4, 2.4, 2.5, 2.12, 2.13, 2.14, 13.6_

- [ ] 6. Move the process job onto `ingest_log_text`
  - `PoliceLogPdfItem` carries the text, not parsed entries; delete `PoliceLogItem` and its test.
  - Add `error_kind`; retry only `download` errors; a PDF with no entries or unreadable text is kind `parse`.
  - Add the runner that exits non-zero when a record moved to `error`, and the advisory lock.
  - Point the `process_urls` DAG spec at the runner.
  - _Requirements: 2.7, 2.8, 2.15, 4.11_

## PR 3: Parser fixes, reprocess, operator commands

About 20 files.

- [ ] 7. Fix the parser
  - Add `PARSER_VERSION`.
  - Parse "Vicinity of:" locations, the "Call Source:" line, every "Refer To" kind, the place code, and the officer code.
  - Move the disposition list to its own module, add every disposition found in the stored PDFs, and set `disposition_unmatched` when none matches.
  - One text fixture and test per gap, cut from the stored PDFs.
  - Document that changing the disposition list means a parser version bump and a reprocess.
  - _Requirements: 1.3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 8. Add the reprocess script
  - `reprocess_police_logs.py --from --to | --all`, in log date order, over `complete` records and `error` records with stored text.
  - Mark repaired `error` records `complete`, log the four counts, take the advisory lock.
  - Tests: no download, no normalization changed, a second run changes no row, a parser version bump alone does not move `updated_at`.
  - A manual `police_log_reprocess` DAG spec.
  - _Requirements: 4.1 to 4.11_

- [ ] 9. Add the operator CLI
  - `errors`, `reset <url>...`, and `unmatched-dispositions`.
  - _Requirements: 2.11, 3.7_

The 343 entries stored before this work are not repaired by reprocess, because the move to `pdf_urls` copied no stored text.
They are repaired when discovery adds their three PDFs again and the process job downloads them.

## PR 4: Normalization records, locations package, correction API

About 34 files.
If it passes 40, the `shared/locations` package (task 11) ships first as its own pull request.
No AI yet.

- [ ] 10. Add provenance to the lookup tables and the `ai_answers` log
  - One mixin; `normalized_type` in place of `subcategory`; the location columns in design.md; the widened `geocoded_via` check.
  - One Alembic migration, covered by the up and down test.
  - Delete the three old categorizer scripts and their tests, which stop working when `subcategory` goes.
  - _Requirements: 6.1, 6.9, 7.1, 7.2, 7.10, 7.13_

- [ ] 11. Add the `shared/locations` package
  - Move `geocode_nominatim` out of `api/`, with the city-bounds check, the 1 per second limiter, and exact or approximate results.
  - Add `public_location`, including the under-100 rule.
  - Add the package to both Dockerfiles.
  - _Requirements: 6.4, 6.7, 6.9, 6.11, 11.6, 11.7_

- [ ] 12. Extend the categories and addresses services and routes
  - Paged lists with source, review mark, and has-normalization filters, and entry counts.
  - PATCH sets `source = 'human'`, clears the review mark, recomputes the public location, rejects a category outside the five with 422, accepts coordinates outside the city bounds.
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
  - Writes never touch `human` rows; `--redo` keeps the old value until a valid new one arrives; every accepted answer goes to `ai_answers`.
  - The per-field summary log and the exit code.
  - Tests with `FakeBackend` for every AI row in design.md's error table.
  - _Requirements: 1.2, 5.1, 5.3, 5.4, 6.1, 7.9, 7.11, 8.6, 8.7, 8.8, 8.10, 8.11, 9.5, 9.6_

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
  - Change the `migrate` service in `compose.yml` from PR 1, and add a separate test fixture, so both drop `marts`, run the migrations, then `dbt run`.
  - Tests: a passing build on good rows, one bad row per check that fails it, and a migration that drops a column a model uses still upgrades.
  - _Requirements: 8.12, 10.7, 11.1, 11.2, 14.1 to 14.6_

## PR 8: API, search sync, and export read the models

About 14 files.

- [ ] 20. Read the models in the admin API and the search sync
  - Map `marts.incidents` on its own metadata, outside `Base`.
  - Incidents API returns raw and normalized values and filters by category, type name, and normalized address; stats count by category and type name.
  - `sync_es.py` reads `marts.incidents` and indexes the normalized fields.
  - _Requirements: 10.1 to 10.7_

- [ ] 21. Read the public models in `report-gen`
  - Plain selects from the three public models; remove the joins and the 2,000 row cap.
  - Keep today's field names and the `addresses.json` shape; write the new fields.
  - The export keeps running from `deploy.sh` at deploy time; its files are not committed.
  - _Requirements: 11.3 to 11.12, 12.9_

## PR 9: Daily schedule and the Airflow image

About 10 files.

- [ ] 22. Add the daily `police_log` DAG
  - A plain DAG file next to `dags/specs.py`: discover, process with a limit of 100, normalize, geocode, dbt build, then sync, with the failure rules in design.md and a final watcher task.
  - A 60 minute timeout per task and a pool of size 1 shared with reprocess.
  - Remove the `discover_urls` and `process_urls` specs.
  - Structure tests.
  - _Requirements: 12.1 to 12.7_

- [ ] 23. Make the AI call run in the Airflow image
  - Install the `claude` CLI and pass the token from `.env`; add a blank entry to `.env.example`.
  - Checked by hand when Connor builds the image: one real AI call from inside the container.
  - _Requirements: 9.1, 9.7, 12.2_

## QA

- [ ] 24. Test each pull request before it is pushed
  - Run the suites.
  - Do a real run of what the pull request adds against `app_test`, never `app`.
  - For PR 5, one real AI batch of 10 values; for PR 6, one evaluation run.
  - Report pass or fail for each criterion the pull request cites, and for the already-met criteria once in PR 1.
