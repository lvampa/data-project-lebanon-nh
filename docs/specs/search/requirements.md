# Search: requirements

**Status:** In progress
**Created:** 2026-06-10
**Updated:** 2026-10-16

## Introduction

City data lives in many tables: properties, incidents, planning meetings and documents, staff, officers, LLCs, and budgets.
An admin who wants everything about one address or one person has to check each page by hand.
Success is one search box in the admin that takes an address, name, or keyword and returns matching records from every entity type, grouped by type.
The same API should be usable by the public web app later.

## Glossary

- **Entity type:** One kind of record with its own search index, like `properties` or `incidents`.
  There are nine: `properties`, `incidents`, `planning_meetings`, `planning_documents`, `city_staff`, `officers`, `llcs`, `budget_line_items`, and `budget_capital_projects`.
- **Address-bearing entity:** An entity type with a street address or venue: properties, incidents, planning meetings, and planning documents.
- **Address normalization:** A row in `address_normalizations` that maps a raw address string to a normalized address with latitude and longitude.
- **Sync:** One run of the job that copies Postgres rows into the search indices.
- **Per-type limit:** The maximum number of results returned for each entity type.

## Requirements

### Requirement 1: Index every entity type

**User story:** As an operator, I want all searchable records copied into Elasticsearch, so that one query can reach every entity type.

#### Acceptance criteria

1. WHEN the sync runs, THE sync script SHALL write every row of each of the nine entity types to an index named after that entity type.
2. THE sync script SHALL include `id` (the Postgres primary key) and `entity_type` in every indexed document.
3. THE sync script SHALL use the Postgres primary key as the document ID, so that running the sync twice leaves one document per row.
4. IF a source table has no rows, THEN THE sync script SHALL skip that index without sending a bulk request.
5. WHEN the sync finishes an index, THE sync script SHALL log the index name and the number of documents written.

### Requirement 2: Attach normalized addresses at index time

**User story:** As an admin, I want records indexed under their normalized address, so that the same place matches no matter how each source spelled it.

#### Acceptance criteria

1. WHEN the sync indexes a property, incident, or planning meeting whose location has an address normalization, THE sync script SHALL store that normalization's `normalized_address`, `lat`, and `lng` on the document.
2. IF an address-bearing record's location has no address normalization, THEN THE sync script SHALL store the raw location as `normalized_address` and leave `lat` and `lng` null.
3. IF an address-bearing record has no location, THEN THE sync script SHALL leave `normalized_address`, `lat`, and `lng` null.
4. WHEN the sync indexes a planning document, THE sync script SHALL copy `normalized_address`, `lat`, and `lng` from the planning meeting with the same `civicclerk_event_id`.
5. IF a planning document has no matching planning meeting, THEN THE sync script SHALL leave its `normalized_address`, `lat`, and `lng` null.
6. THE sync script SHALL load the address normalizations once per run, not once per record.

### Requirement 3: Keep the indices current

**User story:** As an operator, I want the sync to run on its own every night, so that search reflects the latest scraped data without manual steps.

#### Acceptance criteria

1. THE Airflow scheduler SHALL run the `sync_elasticsearch` DAG every day at 03:00 UTC.
2. IF the sync task fails, THEN THE Airflow scheduler SHALL retry it once after 5 minutes.
3. WHEN the DAG is first enabled, THE Airflow scheduler SHALL NOT backfill runs for past dates.

### Requirement 4: Search across all entity types

**User story:** As an admin, I want to search with one query and get results from every entity type, so that I can see everything related to an address or person in one place.

#### Acceptance criteria

1. WHEN a client sends `GET /api/search?q=<query>`, THE search API SHALL return a JSON object with `query`, `normalized_query`, and `results`.
2. THE search API SHALL return a key in `results` for each of the nine entity types, with an empty list for any type with no matches.
3. THE search API SHALL return at most the per-type limit of results for each entity type, ordered by relevance score.
4. THE search API SHALL use a per-type limit of 5 when the `limit` parameter is absent.
5. IF `q` is missing or empty, THEN THE search API SHALL respond with status 422.
6. IF `limit` is below 1 or above 20, THEN THE search API SHALL respond with status 422.
7. THE search API SHALL match terms with a typo tolerance of Elasticsearch `AUTO` fuzziness.
8. THE search API SHALL boost matches on `normalized_address` by a factor of 3, and matches on `location`, `owner`, `name`, `file_name`, and `project_name` by a factor of 2.
9. THE search API SHALL return each result with its `id`, `entity_type`, `score`, and the full indexed document as `data`.

### Requirement 5: Normalize address queries

**User story:** As an admin, I want a typed address matched to its normalized form, so that "304 Hanover St" finds records stored as "304 hanover st lebanon nh".

#### Acceptance criteria

1. WHEN the uppercased query equals a `raw_address` in `address_normalizations`, THE search API SHALL search on that row's `normalized_address`.
2. WHEN the search API searches on a normalized address, THE search API SHALL return it as `normalized_query`.
3. IF the query has no address normalization, THEN THE search API SHALL search on the query as typed and return `normalized_query` as null.
4. THE search API SHALL return the query as typed in `query`, whether or not it was normalized.

### Requirement 6: Admin search page

**User story:** As an admin, I want a search page in the admin, so that I can run cross-entity searches without calling the API by hand.

#### Acceptance criteria

1. THE admin sidebar SHALL link to the search page at `/search`.
2. WHEN the admin submits a query, THE search page SHALL call the search API with the query trimmed of surrounding whitespace.
3. WHILE the query is empty or only whitespace, THE search page SHALL disable the search button and send no request.
4. WHILE a search request is in flight, THE search page SHALL disable the search button and label it "Searching…".
5. WHEN results arrive, THE search page SHALL show one section per entity type that has results, in a fixed order, with the type's label and result count.
6. THE search page SHALL hide sections for entity types with no results.
7. THE search page SHALL show each result's primary field, a secondary field when one exists, and its score to 2 decimal places.
8. WHEN the API returns a `normalized_query` that differs from the submitted query, THE search page SHALL show "Showing results for <normalized_query>".
9. IF the API returns no results for any entity type, THEN THE search page SHALL show "No results found for “<query>”."
10. IF the search request fails, THEN THE search page SHALL show "Search failed. Is the API running?" and log the error to the console.
11. THE search page SHALL link each result to the admin page for that record.
12. THE search page SHALL let the admin collapse and expand each entity type section.

### Requirement 7: Run search locally

**User story:** As a developer, I want Elasticsearch and Kibana in the local stack, so that I can run the sync and inspect indices without extra setup.

#### Acceptance criteria

1. THE compose stack SHALL run a single-node Elasticsearch 8.13.0 on port 9200 with security disabled and a 512 MB heap.
2. THE compose stack SHALL keep Elasticsearch data in a named volume across restarts.
3. THE compose stack SHALL run Kibana 8.13.0 on port 5601, started only after Elasticsearch reports green or yellow health.
4. THE compose stack SHALL give the Airflow services `ELASTICSEARCH_HOST` and start them only after Elasticsearch is healthy.
5. THE Airflow services SHALL load DAGs from the top-level `dags/` directory.

## Out of scope

- Public web search UI. The API is ready for it, but no public page exists yet.
- Geo-distance or map-based search. `lat` and `lng` are stored but not queried.
- Search analytics or query logging.
- Index aliases and zero-downtime re-indexing.
- Tuning field boosts beyond the fixed weights in 4.8.
- Autocomplete and typeahead.
- Removing documents whose Postgres rows were deleted.
  The sync only upserts.
