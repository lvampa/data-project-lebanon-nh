# Planning board: tasks

**Status:** Done
**Created:** 2026-06-03
**Updated:** 2026-10-16

- [x] 1. Add planning tables
  - Add the `PlanningMeeting` and `PlanningDocument` ORM models and export them from `postgres.models`.
  - Add migration `k1l2m3n4o5p6_add_planning.py`, revising `j0k1l2m3n4o5`, with unique CivicClerk id constraints and the three indexes.
  - Make the downgrade drop the indexes, then the tables.
  - _Requirements: 3.1, 3.5, 4.1, 4.9_

- [x] 2. Parse CivicClerk events and files
  - [x] 2.1 Add `parse_event`, with portal URL, null date on a bad or missing start date, and null status when missing.
  - [x] 2.2 Add `parse_file`, with the file type map, the raw-number fallback, and the `streamUrl` or `GetEventFileStream` download URL.
  - [x] 2.3 Add `extract_text_from_pdf`, returning null for empty, non-PDF, or unparseable bytes.
  - Unit test each function in `scripts/tests/test_scrape_civicclerk.py`.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 3. Fetch from the API and upsert
  - [x] 3.1 Open a Chromium context, load the portal home page, and use its request context for API calls.
  - [x] 3.2 Find the planning category by name, and fail with the received names when none matches.
  - [x] 3.3 Page through events 100 at a time, newest first, with `--limit` support.
  - [x] 3.4 Upsert each meeting and each published file, logging a warning and storing null text when a download fails.
  - [x] 3.5 Commit once per run and roll back on any error.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 3.5, 4.8, 4.9, 4.10, 5.4_

- [x] 4. Schedule the scraper
  - Add the `civicclerk_planning` DAG in `dags/scrape/civicclerk_planning.py`, daily at 05:00 UTC, no catchup, one retry after 5 minutes.
  - _Requirements: 5.1, 5.2, 5.3_
