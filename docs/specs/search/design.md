# Search: design

**Status:** In progress
**Created:** 2026-06-10
**Updated:** 2026-11-14

## Overview

One FastAPI endpoint normalizes the query against `address_normalizations` (requirement 4), then runs one Postgres query per entity type and returns the results grouped by type (requirements 1 and 3).
Every query uses the word matching the police log pipeline builds for incident search: whole words by full text, one-edit typos for longer words, and partial identifiers (requirement 2).
The admin page calls the endpoint and renders the groups (requirement 5); its contract does not change.

The first version synced the nine types into Elasticsearch each night.
That version is built and is replaced here; the Decisions section records what it did and why it went.

This ships as one pull request after police log pipeline PR 9, which builds the word matching and the incidents model.
Elasticsearch has since been removed from the stack with the old `/api/search` router, so the endpoint returns with this version and the admin search page gets a 404 until then.

## Architecture

```
              address_normalizations
                       ▲
                       │ 1. normalize query
                       │
GET /api/search ──► api/services/search.py ──► SEARCH_TYPES (nine entries)
                       │                              │
                       │ 2. one query per type         │ fields and joins per type
                       ▼                              ▼
              api/services/text_search.py ──► Postgres tables, and marts.incidents
              (word matching, shared with
               incident search)
```

## Components and interfaces

### Word matching

`api/services/text_search.py`, written by police log pipeline task 20 for incident search and reused here unchanged in its rules.

```python
@dataclass(frozen=True)
class SearchFields:
    short: tuple[ColumnElement, ...]                      # whole words, plus one-edit typos for words of 5+ letters
    long: tuple[ColumnElement, ...] = ()                  # whole words only, against a stored tsvector
    identifiers: tuple[ColumnElement, ...] = ()           # ILIKE for words of 4+ digits and hyphens
    ranking: tuple[ColumnElement, ...] = ()               # the ranking fields in requirement 3.7

def match_all_words(query: str, fields: SearchFields) -> WordMatch
# WordMatch: where clause, hit_ranking_field (boolean expression), score expression
```

- The query is split into words; each word becomes one condition, and the conditions are joined with AND (2.1).
- A word matches when it is in the short fields' tsvector, or in a long field's stored tsvector, or, for 5 or more letters, within one edit of a short field word behind the `word_similarity >= 0.3` prefilter, or, for 4 or more digits and hyphens, inside an identifier (2.2 to 2.6).
- Results sort by three keys: whether any word matched a ranking field, then the score, then the type's date (3.7, 3.8).
  The score adds each word's full-text rank and trigram score.
  A sort key, not a weight, so a strong match in another field can never outrank a ranking-field match.
- These are the same rules and thresholds as incident search; the police log pipeline design explains the 0.3 prefilter and the 5-letter limit.

### Search types

`api/services/search.py` holds one entry per entity type, so the endpoint has no per-type branches.

```python
@dataclass(frozen=True)
class SearchType:
    entity_type: str                  # the results key
    select: Select                    # the rows, with any joins
    fields: SearchFields
    order_by: list[ColumnElement]     # after score; a date column, newest first, where one exists
    hidden: frozenset[str] = frozenset()

SEARCH_TYPES: list[SearchType]        # in the order of the admin page's sections
```

| Entity type | Rows | Ranking fields (3.7) | Date for order | Hidden |
|---|---|---|---|---|
| `properties` | `properties` left-joined to `address_normalizations` on `location` | normalized address, owner, parcel ID | | `owner_address` |
| `incidents` | `marts.incidents` | normalized location, case number | `reported_at` | |
| `planning_meetings` | `planning_meetings` | title | `meeting_date` | |
| `planning_documents` | `planning_documents` | file name | `scraped_at` | `raw_text` |
| `city_staff` | `city_staff` | name | | |
| `officers` | `officers` | name | | |
| `llcs` | `llcs` | name | | |
| `budget_line_items` | `budget_line_items` | GL number, description | `fiscal_year` | |
| `budget_capital_projects` | `budget_capital_projects` | project name, GL number | `fiscal_year` | |

The fields per type are the table in requirement 1.4.
For incidents, the police log pipeline's `search_text` already includes the officer, so this endpoint and `GET /api/incidents?q=` find the same incidents.
Both are admin-only; the public export reads the public models, which leave officers out.

### Search API

`api/routers/search.py` stays thin and keeps its contract.

```
GET /api/search?q=<string, min length 1>&limit=<int 1..20, default 5>
```

1. Look up `q.upper()` in `address_normalizations.raw_address` and use the normalized address if found (4.1 to 4.4).
2. For each entry in `SEARCH_TYPES`, in order, run its select with `match_all_words` inside a savepoint, sort by the three keys, and take `limit` rows (3.3, 3.4).
   If a type's query fails, roll back its savepoint, log the type and the error, and return an empty list for it, so one broken type never fails the search (3.12).
   This keeps the behavior the Elasticsearch version shipped for a missing index.
   The nine queries run one after another; the timing test covers that, so they are not run in parallel unless it fails.
3. Build `SearchResult`s with the row's columns minus the type's hidden fields as `data` (3.9, 3.10).

`SearchResult` and `SearchResponse` in `api/schemas.py` keep their shape, so the admin page needs no change.
`score` is the matching score from Postgres, so its scale differs from Elasticsearch's; the page shows it to 2 decimal places as before.

### Planning document text

Planning documents carry long extracted text, which is too slow to turn into a tsvector on each query.
An Alembic migration adds a stored generated column, `raw_text_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(raw_text, ''))) STORED` (2.6).
The stored column is the gain: nothing is recomputed per query.
A GIN index is added only if the timing test's `EXPLAIN` shows Postgres using it; each word ORs the long field with unindexed short fields, which usually rules a bitmap scan out.

### Admin search page

Unchanged.
It lives in `frontend/admin/app/search/page.tsx`, and `fetchSearch(q)` in `frontend/admin/lib/api.ts` calls the API.
Result links and collapsible sections (5.11, 5.12) are still open, and are frontend work for Connor.

## Data models

No new tables.
One generated column on `planning_documents`, and an index only if the timing test shows it used.
Incidents come from `marts.incidents`, which the police log pipeline's dbt project builds.

## Error handling

| Failure | What happens |
|---|---|
| `q` missing or empty, `limit` out of range | FastAPI returns 422 (3.5, 3.6). |
| A type has no rows yet, such as an empty table | Its key holds an empty list (3.2). |
| One type's query fails, such as `marts.incidents` missing because dbt has not run | That type returns an empty list, the error is logged with the type, and the other types are returned (3.12). |
| Query has no address normalization | Searched as typed; `normalized_query` is null (4.3). |
| Admin request fails | The page shows "Search failed. Is the API running?" (5.10). |

## Testing strategy

- Real-database API tests on the Postgres test harness, with seeded rows of every type:
  - every type's key is present, and an empty type is an empty list;
  - a word in each type's short fields finds it;
  - "Hanovr" finds a property on Hanover St; "Smyth" finds owner Smith;
  - "13339" finds the incident; "4140" finds a budget line by GL number;
  - a word inside a planning document's text finds it, and a typo of that word does not;
  - "St" and "Main" do not fuzzy-match;
  - two words must both match;
  - a normalized address query returns `normalized_query` and finds every raw spelling;
  - a planning document's `raw_text` and a property's `owner_address` never appear in `data`;
  - a record updated in the test shows on the next request;
  - a ranking-field match comes before a stronger match in another field;
  - with one type's table dropped inside the test, that type is empty and the others still return;
  - 422 on missing `q` and on `limit` of 0 and 21.
- A seeded timing test with 100,000 incidents and 10,000 properties and a five-word query that needs the typo path, under 1 second (3.11).
  The pre-push hook skips it; QA runs it.
- The word matching itself is tested by the police log pipeline's task 20.

## Decisions

### Postgres, not Elasticsearch

The first version copied nine tables into nine Elasticsearch indices each night and queried them with one `msearch`.
It worked, but a correction or a new scrape did not show until the next sync, it ran a JVM service for one admin user, and the incident index disagreed with the incidents API about parse errors.
The police log pipeline moved incident search to Postgres, and this spec moves the other eight types onto the same matching.

- Rejected: keep Elasticsearch for the eight other types.
  Two search engines with different typo rules for one search box.
- Rejected: one dbt view that unions all nine types.
  Postgres could not use the planning document index through the union, and the per-type limit needs a query per type anyway.
- Rejected: Postgres full-text search alone.
  It misses typos and partial case numbers, which is why the shared matching exists.

### One query per type from a registry

- Rejected: a branch per type in the endpoint.
  A tenth type is one more `SearchType` entry.

### Keep the response contract

- Rejected: a new response shape with cross-type ranking.
  The admin page works unchanged, and grouped results are what the page shows.

### History from the first version

- Document IDs were Postgres primary keys, and result `data` was the indexed document; `data` is now the row's columns, which keeps the same keys for the page.
- Query normalization stays an exact match on the uppercased query.
- `scripts/ingest/` was named for `import` being a Python keyword, and the scripts and DAG folders were regrouped then; that layout stays.

## Open questions

- Which admin page should each entity type link to, given that some types, such as officers and budget items, have no admin page yet?
- Should the address lookup become the center of the admin later, with one page per address that shows its property, incidents, and planning items?
  That is the product direction, and it would reuse this matching.
