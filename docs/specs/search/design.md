# Search: design

**Status:** Draft
**Created:** 2026-06-10
**Updated:** 2026-11-14

## Overview

This is planned and not built.
`/api/search` was removed with Elasticsearch, so the admin search page gets a 404 until this version lands.

The planned design is one FastAPI endpoint, `GET /api/search?q=&limit=`, that normalizes the query against `address_normalizations`, runs one Postgres query per entity type, and returns the results grouped by type.
Every query would use one shared word matching, which incident search would use too: whole words by full text, one-edit typos for longer words, and partial identifiers.
The admin page already calls the endpoint and renders the groups, so the response shape does not change.

The first version synced nine entity types into Elasticsearch each night.
That version was removed.

## Data flow

```
GET /api/search ──> api/services/search.py ──> SEARCH_TYPES (nine entries)
   1. normalize the query against address_normalizations
   2. per type: select + word matching (api/services/text_search.py) in a savepoint
   3. build results from the row's columns, minus the type's hidden fields
```

- **Word matching** would be shared with incident search.
  The query is split into words, and every word must match (AND).
  A word matches as a whole word in the short fields, as a whole word in a stored tsvector for long text, as a one-edit typo for words of 5 or more letters (behind a `word_similarity >= 0.3` prefilter), or inside an identifier for 4 or more digits and hyphens.
- **Ordering** uses three keys: whether any word matched a ranking field, then the score, then the type's date.
  It is a sort key, not a weight, so a strong match elsewhere never outranks a ranking-field match.
- **Registry:** `SEARCH_TYPES` holds one `SearchType` per entity: properties, incidents, planning meetings, planning documents, city staff, officers, LLCs, budget line items and budget capital projects.
  Each names its select, its short, long, identifier and ranking fields, its order, and the fields it hides (`owner_address`, `raw_text`).
  A tenth type is one more entry.
- **Address normalization:** the uppercased query is looked up in `address_normalizations.raw_address`; if found, the normalized address is searched and returned as `normalized_query`.
- **One type failing** (for example a table that was dropped) returns an empty list for that type, logs it, and the other types still return.
- **Long text:** `planning_documents` gets a stored generated tsvector column, so nothing is recomputed per query.
  A GIN index is added only if the timing test shows Postgres using it.

## Testing

Real-database API tests seed every type and check typos, partial identifiers, two-word AND, ranking order, hidden fields, the normalized address path, a dropped table, and 422 on bad input.
A timing test with 100,000 incidents and 10,000 properties must answer a five-word typo query in under 1 second.
The pre-push hook skips it.

## Decisions

- **Postgres, not Elasticsearch.**
  The first version copied nine tables into Elasticsearch nightly.
  A correction or a new scrape did not show until the next sync, it ran a JVM service for one admin user, and the incident index disagreed with the incidents API.
  Rejected: keeping Elasticsearch for the other eight types, because two engines would apply different typo rules to one search box.
  Rejected: one SQL view that unions all types, because Postgres could not use the planning document index through the union.
  Rejected: plain Postgres full-text search, because it misses typos and partial case numbers.
- **One query per type from a registry.**
  Rejected: a branch per type in the endpoint.
- **Keep the response contract.**
  Rejected: a new shape with cross-type ranking, because the admin page works unchanged with grouped results.

## Open questions

- Which admin page should each entity type link to, when some types have no admin page yet?
- Should the address lookup become the center of the admin, with one page per address showing its property, incidents and planning items?
