# Public privacy: design

**Status:** Draft
**Created:** 2026-11-23
**Updated:** 2026-11-23

## What it is

Two rules for the public static site, applied in two database views that report-gen reads instead of the tables.
A location that names or describes a person publishes only its street; that one is privacy.
Counts, charts and type lists show the AI's plain name for a type, or "Other" when it has none; that one is presentation.
The log's own type text still shows in a place card's details, since the city's report carries it anyway.
The tables, the admin app and the future API keep the full text.

On dev, the AI has a plain name for 351 of 877 raw types ("73 YOM CPR" is "Cardiac arrest"), and about 13,500 entries have a type it has not named yet, so the type normalize run must finish before this ships.

## Data flow

```
normalize (AI)     location answer + names_person  ->  address_normalizations.names_person
public_locations   one row per raw_address: the public name, kind, pin and street
public_log_entries log_entries with the category, the public type and the public location
report-gen         every SQL file reads the two views, never the tables
```

## The flag

`LocationItem` in `scripts/normalize/prompts.py` gains `names_person: bool`.
The prompt says when it is true: a person's name, or a description of a person (age, sex, relation, "juv", "child"), and not a business or building named after someone.
`LOCATION_PROMPT_VERSION` goes to `location-2`, so `uv run normalize --redo` re-asks every location.
A migration adds `names_person boolean NOT NULL DEFAULT false` to `address_normalizations`.
`normalize --redo` never touches a `human` row, and a row becomes `human` whenever a person places its pin (the place sheet, or `PATCH` with coordinates) while its text stays the AI's.
So the migration sets `names_person = true` on every `human` row, and a human row is flagged until a person clears it: it fails closed.
A flag-only AI pass over human rows can come later.

## The views

Both are created in one Alembic migration, the way `public_properties` is.

`public_locations` has one row per `address_normalizations` row:

| Column | Unflagged row | Flagged row |
|---|---|---|
| `raw_address` | as stored; the join key, never selected for output | same |
| `normalized_address` | as stored | its `street` |
| `kind` | as stored | `road` |
| `street` | as stored | same |
| `names_person` | false | true |
| `lat`, `lng` | as stored | null; `places.sql` puts its calls on its street's pin |
| `coordinate_precision` | as stored | `approximate` |

For a flagged row, the pin is its street's, chosen the way `places.sql` already hangs an approximate place on its street (the `links` CTE): the busiest bare-street pin with the same `street`, then the lowest id.
The view exposes the flag, and `places.sql` applies that one rule to both, so there is no second, weaker match on text.
So `places.sql` must keep flagged entries past its `lat IS NOT NULL` filter until they are linked.
With no street pin, the entry is off the map, as an unplaced location is today.
A row whose `normalized_address` is null (an AI miss) has no public name either, so it is treated like a flagged row with no street.

`public_log_entries` is `log_entries` with three columns replaced:
- `category` is `call_category(incident_type, call_source)` on the full type, so category counts are unchanged.
- `incident_type` is `incident_type_categories.normalized_type`, or "Other" when the type has no plain name.
- `raw_incident_type` is the log's text, which only the place card's details select.
- `location` is the public `normalized_address`, joined through `public_locations`, or null when the location was never normalized, since text with no flag may still name someone.

`raw_location` keeps the log text for the join to `public_locations`, and no export selects it.

## Export changes

Each file in `tools/report-gen/src/sql/` swaps `log_entries` for `public_log_entries` and `address_normalizations` for `public_locations`.
Every query reads the view's `category` and never calls `call_category()` itself, since the view's type may be "Other" and a recomputed category would move a rare traffic or alarm entry to premises.
Both `addresses.json` and `activity.json` count off that one column, so they keep matching.
`places.sql` joins on `raw_location` and takes `MODE()` of the public `location` for the pin's spelling, so the exported `raw_address` is public too.
A Rust test reads every `.sql` file and fails if one names either table or calls `call_category(`, so a new query cannot skip the rules.
"Other" is listed last in type lists and charts, whatever its count.

## Rejected

- Dropping flagged text at normalize: the API needs it.
- Rules on words for people ("yo", "juv", "male"): they miss plain names.
- Showing a raw type as "Other" when it is seen under 3 times: it hides useful one-offs, and passes a repeated note like "DEP INFO - <name>", which is poor presentation whatever its count.
- Hiding the raw type everywhere: the card's details are where a reader looks for the log's own words.
