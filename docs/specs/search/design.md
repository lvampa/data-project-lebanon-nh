# Search: design

**Status:** In progress
**Created:** 2026-06-10
**Updated:** 2026-10-16

## Overview

A sync script copies nine Postgres entity types into one Elasticsearch index each, attaching normalized addresses as it goes (requirements 1 and 2).
A nightly Airflow DAG runs the sync (requirement 3).
A FastAPI endpoint normalizes the query against `address_normalizations`, runs one `msearch` across all nine indices, and returns results grouped by entity type (requirements 4 and 5).
An admin page calls the endpoint and renders the groups (requirement 6).
Elasticsearch and Kibana run in the compose stack for local work (requirement 7).

Everything except result links and collapsible sections (6.11, 6.12) is built.

## Architecture

```
Postgres ──► scripts/sync/sync_es.py ──► Elasticsearch (9 indices)
   ▲               ▲                            │
   │      dags/sync/sync_elasticsearch.py       │
   │           (03:00 UTC nightly)              │
   │                                            ▼
   └── address_normalizations ◄── api/routers/search.py  GET /api/search
                                                │
                                   frontend/admin/app/search/page.tsx
```

The API reads Postgres only for query normalization.
All matching happens in Elasticsearch.

## Components and interfaces

### Sync script

Lives in `scripts/sync/sync_es.py`.
Run with `uv run python scripts/sync/sync_es.py` from the repo root.
Reads `ELASTICSEARCH_HOST` (default `http://localhost:9200`) and the usual Postgres settings through `postgres.SessionLocal`.

- `get_address_lookup(session) -> dict[str, dict]` loads every address normalization once, keyed by `raw_address`.
- One `build_*_doc(row, ...) -> dict` function per entity type turns an ORM row into a document.
  Address-bearing builders take the address lookup.
  `build_planning_document_doc` takes a meeting lookup keyed by `civicclerk_event_id`, built from the planning meetings in the same run.
- `sync_index(es, index, rows, build_fn) -> int` sends one `helpers.bulk` request of `index` actions with `_id = str(row.id)` and returns the count.
  It returns 0 without calling Elasticsearch when `rows` is empty.
- `main()` configures Logfire, opens a session, builds both lookups, and syncs each index inside a `sync index` span.

Incidents come from the `LogEntry` model.

### Sync DAG

Lives in `dags/sync/sync_elasticsearch.py`.

| Setting | Value |
|---|---|
| `dag_id` | `sync_elasticsearch` |
| `schedule` | `0 3 * * *` |
| `start_date` | 2026-06-10 UTC |
| `catchup` | `False` |
| Task | `sync_es`, a `BashOperator` running `cd /opt/project && uv run --frozen python scripts/sync/sync_es.py` |
| Retries | 1, after 5 minutes |

### Search API

Lives in `api/routers/search.py`, mounted in `api/main.py` at `/api/search`.
The Elasticsearch client is a lazy module-level singleton built from `ELASTICSEARCH_HOST`.

```
GET /api/search?q=<string, min length 1>&limit=<int 1..20, default 5>
```

Request handling:

1. Look up `q.upper()` in `address_normalizations.raw_address`.
   Use the matching `normalized_address` as the search text if found, else `q`.
2. Send one `msearch` with one search per index, in the order of `ES_INDICES`.
   Each search is a `multi_match` with `fuzziness: AUTO`, `size: limit`, and these fields:

   ```
   normalized_address^3, location^2, owner^2, name^2, file_name^2, project_name^2, *
   ```

3. Zip the responses back to index names and build the grouped response.
   A null `_score` becomes `0.0`.

Response schemas in `api/schemas.py`:

```python
class SearchResult(BaseModel):
    id: int
    entity_type: str
    score: float
    data: dict[str, Any]   # the indexed _source document

class SearchResponse(BaseModel):
    query: str                         # as typed
    normalized_query: str | None       # null when no normalization matched
    results: dict[str, list[SearchResult]]  # one key per index, always all nine
```

Example:

```json
{
  "query": "304 Hanover St",
  "normalized_query": "304 hanover st lebanon nh",
  "results": {
    "properties": [
      {"id": 1, "entity_type": "properties", "score": 4.2,
       "data": {"id": 1, "entity_type": "properties", "location": "304 HANOVER ST", "owner": "SMITH JOHN"}}
    ],
    "incidents": [],
    "planning_meetings": []
  }
}
```

### Admin search page

Lives in `frontend/admin/app/search/page.tsx`, a client component.
`fetchSearch(q)` in `frontend/admin/lib/api.ts` calls the API.
`SearchResult` and `SearchResponse` types live in `frontend/admin/lib/types.ts`.
The sidebar (`frontend/admin/components/sidebar.tsx`) has a Search item in the Operations section.

- Sections render in a fixed order from `ENTITY_LABELS`, and empty sections are hidden.
- Each card shows a primary field (first non-empty of `location`, `owner`, `name`, `file_name`, `project_name`, `description`, else `ID <id>`), an optional secondary field (first of `incident_type`, `title`, `department`, `fund_name`), and the score.
- The page tracks the submitted query separately from the input, so the "Showing results for" note compares against what was searched, not what is being typed.
- Cards do not link anywhere yet, and sections are not collapsible.

### Compose stack

`compose.yml` adds:

- `elasticsearch`: `docker.elastic.co/elasticsearch/elasticsearch:8.13.0`, `discovery.type: single-node`, `xpack.security.enabled: "false"`, `ES_JAVA_OPTS: -Xms512m -Xmx512m`, port 9200, volume `elasticsearch_data`.
  Healthcheck curls `/_cluster/health` for green or yellow every 15 s, 5 retries, 60 s start period.
- `kibana`: `docker.elastic.co/kibana/kibana:8.13.0`, port 5601, depends on a healthy `elasticsearch`.
- Airflow common env gets `ELASTICSEARCH_HOST: http://elasticsearch:9200`, and the shared `depends_on` waits for a healthy `elasticsearch`.
- The Airflow DAGs mount is `./dags:/opt/airflow/dags`.

`elasticsearch>=8.0.0` is a dependency of `api/pyproject.toml` and of the root `dev` dependency group.

### Repo layout changes

The feature also reorganized two directories, so the sync job had a home:

- `scripts/` is grouped by action: `scrape/`, `ingest/`, `export/`, `sync/`, each a package.
  A `generate/` group was created too, then removed on 2026-09-07 with the superseded Python report generator.
- DAGs moved from `scrapers/dags/` to top-level `dags/`, grouped as `scrape/`, `process/`, and `sync/`.
  DAGs that call scripts use the new paths.

## Data models

One index per entity type, with dynamic mappings.
Every document has `id` and `entity_type`.
Address-bearing documents also have `normalized_address`, `lat`, and `lng`.

| Index | Source model | Fields |
|---|---|---|
| `properties` | `Property` | `parcel_id`, `location`, `owner`, `owner_address`, `land_use`, `assessed_total` (float), `year_built`, address fields |
| `incidents` | `LogEntry` | `case_number`, `incident_type`, `location`, `officer`, `disposition`, `reported_at` (ISO 8601), `raw_text`, address fields |
| `planning_meetings` | `PlanningMeeting` | `civicclerk_event_id`, `title`, `category`, `meeting_date` (ISO 8601), `status`, `location`, address fields |
| `planning_documents` | `PlanningDocument` | `civicclerk_file_id`, `civicclerk_event_id`, `file_name`, `file_type`, `raw_text`, address fields from the parent meeting |
| `city_staff` | `CityStaff` | `name`, `title`, `department`, `division` |
| `officers` | `Officer` | `name`, `rank`, `division` |
| `llcs` | `Llc` | `name`, `raw_owner_name` |
| `budget_line_items` | `BudgetLineItem` | `fiscal_year`, `department`, `description`, `fund_name` |
| `budget_capital_projects` | `BudgetCapitalProject` | `fiscal_year`, `project_name`, `fund_name` |

Planning meeting `location` is usually a venue like "City Hall", so it usually falls back to the raw value.

## Error handling

| Failure | What happens |
|---|---|
| Location has no normalization | Raw location is indexed as `normalized_address`; `lat` and `lng` are null. |
| Location is null | All three address fields are null. |
| Planning document has no parent meeting | All three address fields are null. |
| Empty source table | `sync_index` skips the bulk call and returns 0. |
| Sync task fails | Airflow retries once after 5 minutes. |
| `q` missing or empty, `limit` out of range | FastAPI returns 422. |
| Elasticsearch unreachable | Unhandled; the API returns 500. |
| An index does not exist yet | Unhandled; the `msearch` item has `error` instead of `hits`, which raises and returns 500. |
| Admin request fails | The page shows "Search failed. Is the API running?" and logs to the console. |

## Testing strategy

- `scripts/tests/test_sync_es.py` unit-tests `get_address_lookup` (populated and empty), every `build_*_doc` function including the address fallback, and `sync_index` with `bulk` patched (action shape and the empty no-op).
  No Elasticsearch or Postgres connection is needed.
- `api/tests/test_search.py` tests the endpoint through `TestClient` with `get_db` overridden and `Elasticsearch` patched: grouped results, all-empty results, normalized query present, normalized query null, and 422 on missing `q`.
  A fixture resets the client singleton between tests.
- Not tested: the DAG, the compose services, the admin page, `limit` validation, and Elasticsearch failure paths.
- No tests run against a live Elasticsearch in CI.

## Decisions

- **One index per entity type, not one shared index.**
  Each type keeps its own fields and mapping, and `msearch` gives a separate top-N per type, which is what the grouped response needs.
- **Document ID is the Postgres primary key.**
  Re-runs overwrite in place, so the sync needs no state.
  The cost is that deleted rows are never removed (see Out of scope in the requirements).
- **Normalize addresses at sync time, not query time.**
  The lookup is loaded once per run and joined in Python, which keeps queries to a single Elasticsearch round trip.
- **Query normalization is an exact match on the uppercased query.**
  It is cheap and correct for addresses typed the way the sources write them.
  Anything else falls through to fuzzy matching.
- **`scripts/ingest/` instead of `scripts/import/`.**
  The design named it `import/`, but `import` is a Python keyword and cannot be a package name.
- **Field boosts and fuzziness were added in the plan.**
  The design only boosted `normalized_address^3`.
  The built query also boosts `location`, `owner`, `name`, `file_name`, and `project_name` by 2 and uses `fuzziness: AUTO`.
- **Results carry the source document under `data`.**
  The design showed entity fields flattened onto each result.
  The built schema nests them, so `SearchResult` has a fixed shape for any entity type.
- **`msearch(searches=...)`, not `body=`.**
  The plan used `body=`; the code switched to `searches=`, the keyword the 8.x client documents for `msearch`.
- **Healthchecks and dependency ordering were added beyond the design.**
  Kibana and the Airflow services wait for Elasticsearch to be healthy, and the healthcheck has a 60 s start period so a slow boot is not marked unhealthy.
- **The sync script has no `ES_INDICES` list.**
  The design defined one there too, but only the API uses it; the sync's index names live in its `syncs` table in `main()`.
- **Result links and collapsible sections were not built.**
  The design asked for both (6.11, 6.12).
  The plan dropped them, and the page shipped with flat, unlinked cards.
- **Kibana is included for local inspection only.**
  It is not used by any code path.

## Open questions

- The `api` compose service does not set `ELASTICSEARCH_HOST` or depend on `elasticsearch`, so inside compose it would try `localhost:9200`.
  Should it get the same env and dependency as the Airflow services?
- The Airflow image neither copies nor mounts `scripts/`, so `cd /opt/project && uv run --frozen python scripts/sync/sync_es.py` may not find the script in the container.
  The same applies to the DAGs that call `scripts/scrape/`.
  This needs a check against a running stack.
- Should the API return empty results instead of 500 when an index is missing or Elasticsearch is down?
- Which admin page should each entity type link to, given that some types (officers, budget items) have no admin page yet?
