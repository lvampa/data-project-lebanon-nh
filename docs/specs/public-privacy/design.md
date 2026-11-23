# Public privacy: design

**Status:** Draft
**Created:** 2026-11-23
**Updated:** 2026-11-23

## What it is

Two rules for the public static site, applied in two database views that report-gen reads instead of the tables.
A location that names or describes a person publishes only its street.
An incident type seen fewer than 3 times publishes as "Other".
The tables, the admin app and the future API keep the full text.

On dev, 674 types appear under 3 times, covering 749 of 27,462 entries (2.7%).
They are mostly dispatch notes: "DEP INFO - M-ARTHUR", "14 MONTH F, FALLS HIT HEAD", "INFANT WITH BLOOD IN MOUTH".

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
A `human` row keeps false until the admin can set it.

## The views

Both are created in one Alembic migration, the way `public_properties` is.

`public_locations` has one row per `address_normalizations` row:

| Column | Unflagged row | Flagged row |
|---|---|---|
| `raw_address` | as stored; the join key, never selected for output | same |
| `normalized_address` | as stored | its `street` |
| `kind` | as stored | `road` |
| `street` | as stored | same |
| `lat`, `lng` | as stored | its street's pin, or null |
| `coordinate_precision` | as stored | `approximate` |

For a flagged row, the pin is the street's: the first placed `address_normalizations` row whose `normalized_address` is the flagged row's `street`.
With no such row, `lat` and `lng` are null, so the place and activity queries leave the entry off the map, as they already do for an unplaced location.
The precision is `approximate`.

`public_log_entries` is `log_entries` with three columns replaced:
- `category` is `call_category(incident_type, call_source)` on the full type, so category counts are unchanged.
- `incident_type` is "Other" when the type appears under 3 times among parsed entries.
- `location` is the public `normalized_address`, joined through `public_locations`, or null when the location was never normalized, since text with no flag may still name someone.

`raw_location` keeps the log text for the join to `public_locations`, and no export selects it.

## Export changes

Each file in `tools/report-gen/src/sql/` swaps `log_entries` for `public_log_entries` and `address_normalizations` for `public_locations`.
`places.sql` already takes `MODE()` of the location for the pin's spelling, which becomes the public name.
A Rust test reads every `.sql` file and fails if one names either table, so a new query cannot skip the rules.

## Rejected

- Dropping flagged text at normalize: the API needs it.
- Rules on words for people ("yo", "juv", "male"): they miss plain names.
- An AI pass over incident types: it costs calls and a review step, and the count rule catches the one-offs.
- Counting types within the export window: the public type of an entry would change as the window moves.

## Open questions

- Should the threshold count distinct days, so one busy night of a one-off note does not reach 3?
