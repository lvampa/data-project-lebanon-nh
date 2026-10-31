# PDF URL queue: tasks

**Status:** In progress
**Created:** 2026-10-31
**Updated:** 2026-10-31

- [ ] 1. Add the `pdf_urls` table
  - Add the `PdfUrl` ORM model and one Alembic migration revising `22fc0163d5ff`, with a downgrade that drops it.
  - Add a constraint case for `state` to `test_migrations.py`.
  - _Requirements: 2.3, 3.1, 4.1_

- [ ] 2. Write discovered URLs to Postgres
  - Port `UrlRecordPipeline` to a multi-row insert with `ON CONFLICT (canonical_url) DO NOTHING`.
  - Make `UrlRecord.log_date` a `date`.
  - Port the pipeline tests.
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 3. Claim and requeue in Postgres
  - Port `ProcessUrlsSpider.start()` to the requeue statements and the `SKIP LOCKED` claim in one transaction.
  - Replace `UrlDocument` with `PdfUrlClaim`.
  - Port the error marking in the errback and parse paths.
  - Test the claim statement under the Postgres dialect, the requeue rules, and the error paths.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 4.4, 4.5_

- [ ] 4. Complete URLs in the entries transaction
  - Update `pdf_urls` in the same commit as the entry inserts in `PoliceLogPipeline`.
  - Test with `FakeSession` that one commit holds both, and that a failure commits only the `error` update.
  - _Requirements: 4.1, 4.2, 4.3_

- [ ] 5. Remove MongoDB
  - Delete `shared/mongo`, its workspace member, the `mongo` and `pymongo` dependencies, and relock.
  - Remove the `mongo` service, volume and `MONGO_*` variables from `compose.yml`, `.env.example` and the Dockerfiles.
  - Update `AGENTS.md`, `scrapers/CLAUDE.md`, `scrapers/README.md` and `.cursor/rules`.
  - Check that `docker compose config -q` passes without `MONGO_*` set.
  - _Requirements: 5.1, 5.2, 5.3_
