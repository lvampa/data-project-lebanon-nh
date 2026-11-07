# Search: requirements

**Status:** In progress
**Created:** 2026-06-10
**Updated:** 2026-11-07

## Introduction

City data lives in many tables: properties, incidents, planning meetings and documents, staff, officers, LLCs, and budgets.
An admin who wants everything about one address or one person has to check each page by hand.
Success is one search box in the admin that takes an address, name, case number, or keyword and returns matching records from every entity type, grouped by type.
It is the first step toward one lookup that connects everything: an address to its incidents, owners, and staff.

Search first ran on Elasticsearch, synced nightly.
It now runs in Postgres, on the same word matching as the police log pipeline's incident search, so results are current on every request and there is no second copy of the data to keep in step.

## Glossary

- **Entity type:** One kind of searchable record.
  There are nine: `properties`, `incidents`, `planning_meetings`, `planning_documents`, `city_staff`, `officers`, `llcs`, `budget_line_items`, and `budget_capital_projects`.
- **Short field:** A searchable field that holds a name, address, title, or label, such as a property's owner or a staff member's title.
- **Long field:** A searchable field that holds document text: a planning document's extracted text.
- **Identifier field:** A searchable field that holds a code: a case number, a parcel ID, or a GL number.
- **Address normalization:** A row in `address_normalizations` that maps a raw address string to a normalized address.
- **Per-type limit:** The maximum number of results returned for each entity type.
- **Hidden field:** A field the search API never returns: a document's extracted text and a property owner's mailing address.

## Requirements

### Requirement 1: Search every entity type in Postgres

**User story:** As Connor, I want search to read the live tables, so that a record I just corrected or scraped shows up on my next search.

#### Acceptance criteria

1. THE search API SHALL search all nine entity types in Postgres, with no separate search index.
2. WHEN a record changes in Postgres, THE search API SHALL return the change on the next request, with no sync or build.
3. THE search API SHALL search incidents through the police log pipeline's consumer models, so that incident search agrees with the incidents API on what an incident is.
4. THE search API SHALL search, per entity type, these fields:

   | Entity type | Short fields | Long fields | Identifier fields |
   |---|---|---|---|
   | `properties` | location, normalized address, owner, land use | | parcel ID |
   | `incidents` | raw and normalized type, category, raw and normalized location, disposition, officer | | case number |

   Officer names are searchable in the admin only; no public page or export searches or shows them.
   | `planning_meetings` | title, category, location | | |
   | `planning_documents` | file name | extracted text | |
   | `city_staff` | name, title, department, division | | |
   | `officers` | name, rank, division | | |
   | `llcs` | name, raw owner name | | |
   | `budget_line_items` | description, department, fund name | | GL number |
   | `budget_capital_projects` | project name, fund name | | GL number |

### Requirement 2: Match words the same way for every type

**User story:** As Connor, I want one set of matching rules everywhere, so that a typo or a partial case number behaves the same whether I am looking for a property or an incident.

#### Acceptance criteria

1. WHEN a query has more than one word, THE search API SHALL return only records that match every word, each word in any of the record's searchable fields.
2. THE search API SHALL match a word that appears as a whole word in a short or long field.
3. WHEN a query word of 5 or more letters has one letter missing, extra, or wrong compared with a word in a short field, THE search API SHALL still match it.
4. THE search API SHALL match words of 4 letters or fewer exactly, with no typo tolerance.
5. WHEN a query word of at least 4 digits and hyphens is part of an identifier field, such as "13339" for "26-13339" or "4140" for "1100-4140-0000-1100-0000", THE search API SHALL match it.
6. THE search API SHALL match long fields as whole words only, with no typo tolerance.

### Requirement 3: Return results grouped by entity type

**User story:** As Connor, I want results from every entity type in one response, so that I can see everything related to an address or person in one place.

#### Acceptance criteria

1. WHEN a client sends `GET /api/search?q=<query>`, THE search API SHALL return a JSON object with `query`, `normalized_query`, and `results`.
2. THE search API SHALL return a key in `results` for each of the nine entity types, with an empty list for any type with no matches.
3. THE search API SHALL return at most the per-type limit of results for each entity type.
4. THE search API SHALL use a per-type limit of 5 when the `limit` parameter is absent.
5. IF `q` is missing or empty, THEN THE search API SHALL respond with status 422.
6. IF `limit` is below 1 or above 20, THEN THE search API SHALL respond with status 422.
7. WHEN two records of one entity type both match every word, and only one matches a word in a ranking field, THE search API SHALL return that one first.
   The ranking fields are: properties, normalized address, owner, and parcel ID; incidents, normalized location and case number; planning meetings, title; planning documents, file name; staff, officers, and LLCs, name; budget line items, GL number and description; capital projects, project name and GL number.
8. WHEN two records of one type rank the same under 3.7, THE search API SHALL order them by match score, then newest first where the type has a date.
9. THE search API SHALL return each result with its `id`, `entity_type`, `score`, and the record's fields as `data`.
10. THE search API SHALL NOT return hidden fields in `data`.
11. WHILE the database holds 100,000 incidents and 10,000 properties, THE search API SHALL answer a query of up to five words within 1 second.
12. IF the query for one entity type fails, THEN THE search API SHALL return an empty list for that type, return the other types' results, and log which type failed.

### Requirement 4: Normalize address queries

**User story:** As Connor, I want a typed address matched to its normalized form, so that "304 Hanover St" finds records stored as "304 hanover st lebanon nh".

#### Acceptance criteria

1. WHEN the uppercased query equals a `raw_address` in `address_normalizations`, THE search API SHALL search on that row's `normalized_address`.
2. WHEN the search API searches on a normalized address, THE search API SHALL return it as `normalized_query`.
3. IF the query has no address normalization, THEN THE search API SHALL search on the query as typed and return `normalized_query` as null.
4. THE search API SHALL return the query as typed in `query`, whether or not it was normalized.

### Requirement 5: Admin search page

**User story:** As Connor, I want a search page in the admin, so that I can run cross-entity searches without calling the API by hand.

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

## Out of scope

- Public search for residents.
  There is no public search today.
  A resident is more likely to want "what is happening near this address" than a keyword box: an address lookup that shows nearby incidents, the property, and planning items on the map.
  That is a later feature, built on the same matching, and it would leave out officers, owners' mailing addresses, and staff contact details.
- Ranking across entity types.
  Results stay grouped by type.
- Geo-distance or map-based search.
- Search analytics or query logging.
- Autocomplete and typeahead.
- Query operators such as `-word`, quoted phrases, and `or`.
- Removing Elasticsearch from the stack.
  The police log pipeline spec has that follow-up task; this spec stops reading it.
