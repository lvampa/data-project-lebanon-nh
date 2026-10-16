# Search: tasks

**Status:** In progress
**Created:** 2026-06-10
**Updated:** 2026-10-16

- [x] 1. Group `scripts/` by action
  - Move the scrape, import, and export scripts into `scripts/scrape/`, `scripts/ingest/`, and `scripts/export/`, and add an empty `scripts/sync/` package.
  - Update the import paths in the existing script tests and confirm the suite still passes.
  - _Requirements: 3.1_

- [x] 2. Move DAGs to a top-level `dags/` directory
  - Move the scraping DAGs to `dags/scrape/` and the processing DAGs to `dags/process/`, and add `dags/sync/`.
  - Point `civicclerk_planning` and `llc_lookup` at the new script paths.
  - Change the Airflow DAGs mount to `./dags` and delete `scrapers/dags/`.
  - _Requirements: 7.5_

- [x] 3. Add Elasticsearch and Kibana to the compose stack
  - Add the `elasticsearch` service with a healthcheck and the `elasticsearch_data` volume.
  - Add the `kibana` service, started after Elasticsearch is healthy.
  - Give the Airflow services `ELASTICSEARCH_HOST` and a dependency on a healthy Elasticsearch.
  - Add `elasticsearch>=8.0.0` to `api/pyproject.toml` and the root `dev` group.
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 4. Build the sync script
  - [x] 4.1 Add `get_address_lookup` and the raw-address fallback, with tests for a populated and an empty table.
  - [x] 4.2 Add a `build_*_doc` function for each of the nine entity types, with a test for each and a test for the fallback.
  - [x] 4.3 Add planning document address inheritance through a meeting lookup, with a test.
  - [x] 4.4 Add `sync_index` with a bulk call keyed by Postgres ID, with tests for the action shape and the empty no-op.
  - [x] 4.5 Add `main()` to sync all nine indices with a Logfire span and count per index.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 5. Schedule the sync nightly
  - Add the `sync_elasticsearch` DAG at 03:00 UTC with one retry after 5 minutes and no catchup.
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 6. Add the search endpoint
  - Add `SearchResult` and `SearchResponse` to `api/schemas.py`.
  - Add `GET /api/search` with query normalization, one `msearch` across all nine indices, and grouped results, and register it in `api/main.py`.
  - Test grouped results, all-empty results, normalized query present and null, and 422 on a missing `q`.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.1, 5.2, 5.3, 5.4_

- [x] 7. Add the admin search page
  - Add `fetchSearch` and the search types to the admin API client.
  - Add a Search item to the sidebar.
  - Add `/search` with the form, loading state, grouped result sections, normalized-query note, no-results message, and error message.
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10_

- [ ] 8. Link and collapse search results
  - [ ] 8.1 Link each result card to the admin page for its record.
  - [ ] 8.2 Make each entity type section collapsible.
  - Add a test for the link targets per entity type.
  - _Requirements: 6.11, 6.12_
