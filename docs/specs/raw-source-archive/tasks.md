# Raw source archive: tasks

**Status:** Draft
**Created:** 2026-11-06
**Updated:** 2026-11-13

The work ships as three pull requests of 10 to 40 files each.
PR 1a ships between police log pipeline PR 1 and PR 2; PRs 1b and 1c ship before police PR 2b, which drops the raw text columns.
There is no gate before 2b: nothing is live, so the databases are reset and rescraped (2026-11-13).
File counts are estimates and include tests.

| PR | What ships | Files |
|---|---|---|
| 1a | Test harness, archive class, middleware, indexes at startup | about 20 |
| 1b | Archive reads, AI call log, LLC and budget sources, parcel replay, versions command | about 16 |
| 1c | Backup and check command | about 10 |

## PR 1a: Write the archive

About 20 files.
The three spec files ride along in this pull request.

- [x] 1. Add the MongoDB test harness
  - A pytest plugin in `shared/mongo`, loaded through a `pytest11` entry point: set `MONGO_DB=scraped_data_test`, stop if the name does not end in `_test`, drop the archive collection after each test.
  - A healthcheck on the `mongo` compose service, and CI starting `mongo` next to `postgres`.
  - Install `mongodb-database-tools` in `docker/Dockerfile.airflow`, for the backup DAG.
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 2. Add the archive class and indexes
  - `RawArchive` with hashing, page-state removal, gzip, the 15 MB limit, batched upserts, counts, and the 2 second selection and 5 second operation timeouts that mark it down.
  - The three indexes in `init_indexes`, run after Alembic by hand (`uv run migrate`, since #26 removes the `migrate` service).
  - Tests for every row in design.md's error table that belongs to writing.
  - _Requirements: 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3_

- [x] 3. Add the middleware and opt in the two spiders
  - `RawArchiveMiddleware` at downloader priority 50, `RAW_ARCHIVE_ENABLED`, and `archive_source` and `archive_key` on the process and VGSI spiders.
  - Batch size 1 for the process spider, with `response.meta["archived"]` set from the write result; 50 for VGSI.
  - Tests: both spiders archive their pages; street pages, non-200 responses, cached responses, and other spiders do not; a gzip-encoded response is archived decompressed; the setting turns it off.
  - Test with MongoDB unreachable: the police entries are still stored. The exit-code half lands in police log PR 2, with the runner.
  - _Requirements: 1.1, 1.2, 1.7, 1.8, 3.3, 3.4, 3.5, 3.7, 3.8, 5.4_

## PR 1b: Read, extend, and replay the archive

About 16 files.

- [x] 4. Add the archive reads and the AI call log
  - `RawArchive.newest` and `RawArchive.by_hash`, for the police log reprocess.
  - `AiCallLog` with its indexes, returning `None` when a write fails.
  - _Requirements: 4.1, 6.1 to 6.5_

- [x] 5. Archive the LLC pages and budget PDFs
  - `scrape_llcs.py` archives each business page as `nh_sos_business`; `download_budget_pdfs.py` archives each PDF and its text as `budget_pdf`.
  - Tests: each script archives its download, and an unreachable Mongo leaves the LLC rows and budget text files unchanged.
  - _Requirements: 1.9, 1.10, 8.1_

- [x] 6. Add the parcel replay command
  - Parcel replay through `parse_parcel` and `PropertyPipeline`; police PDFs are replayed by the police log reprocess job.
  - Tests: replay of one saved parcel page matches a normal ingest; no download; no archive write; truncated and missing versions are counted.
  - _Requirements: 4.2, 4.3, 4.4_

- [x] 7. Add the versions command
  - One key's versions, newest first.
  - Document `replay` and `versions` in `scrapers/README.md`.
  - _Requirements: 4.6_


## PR 1c: Data safety

About 10 files.
This is the pull request Connor should read most closely, with police PR 2b: together they keep the only copy of the parser's input.

- [x] 8. Entry texts moved to the police log pipeline
  - The `police_log_entry_text` writes ship in police PR 2, with the ingest they follow.
  - The legacy copy and the migration guard are dropped (2026-11-13); police PR 2b's migration becomes a plain column drop.
  - _Requirements: 8.2, 8.10_

- [x] 9. Add the daily backup
  - The `mongo_backup` script with `mongodump --gzip --archive` into a new dated file in `/opt/backups/mongo`, run by hand.
  - The bind mount in `compose.yml`, `${MONGO_BACKUP_DIR:-${HOME}/backups/data-project/mongo}:/opt/backups/mongo`, on the Airflow services, and a commented `MONGO_BACKUP_DIR` entry in `.env.example` showing the default.
  - The DAG's first step checks the folder is writable and fails with a message naming it when it is missing or not writable.
  - `scrapers/README.md` says to create `~/backups/data-project/mongo` on the host before the first run, owned by the user that runs Docker, because a folder Docker creates is owned by root and the Airflow user cannot write to it.
  - Test: the writable check fails with the message on a read-only folder.
  - `raw_sources restore-check` to restore into a `_test` database and compare counts.
  - A DAG structure test.
  - _Requirements: 7.1 to 7.5_

- [x] 10. Add the check command
  - Size and versions per source with the 5 GB warning.
  - Log PDFs with an archived body, counted; log PDFs with none; parcels with no version; `ai` normalizations with a null `ai_call_id`.
    The text-only count goes, with `police_log_text` (2026-11-13).
  - The `ai_call_id` line lands with police log PR 4, which adds the normalization tables.
  - Document `check` and `restore-check` in `scrapers/README.md`.
  - _Requirements: 2.5, 4.5_

## QA

- [ ] 11. Test each pull request before it is pushed
  - Run the suites against `app_test` and `scraped_data_test`, never the live databases.
  - For PR 1a, a real run of the process job on the three known PDFs and of the VGSI spider on a few parcels, then a second run to show the seen counts move and no new versions appear.
  - Measure the overhead in 3.6 on 100 PDFs with the archive on and off.
  - For PR 1b, replay parcels and compare with the live-download results.
  - For PR 1c, a backup and a restore check into a test database.
  - Report pass or fail for each criterion.
