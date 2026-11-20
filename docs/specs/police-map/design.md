# Police map: design

**Status:** In progress
**Created:** 2026-11-19
**Updated:** 2026-11-19

## What it is

The map page shows where Lebanon's police calls happen in 2026.
One kind of pin marks a place, sized by how many calls name it.
Clicking a pin opens a report card for that place: what kinds of calls, what happened, how they ended, and the latest calls.
With nothing selected, the panel summarizes the town and lists the busiest places.
The card reports data.
It adds no commentary and no trend.

## Data flow

```
log_entries + address_normalizations
  └─ report-gen (places.sql, one query, filtered to log_date >= --since)
       addresses.json         one row per pin, for the map and the rank
       places/<id>.json       one report card per pin
       stats.json             the town summary
  └─ frontend/web             loads addresses.json and stats.json up front, a card on click
```

A pin is one normalized address with its coordinates, so two spellings of a place are one pin.
`call_category()` in the database puts each call in one of five categories from its incident type and call source: traffic, checks, alarms, paperwork or premises.
A road is a pin whose normalized address has no `, `, such as a bare street, an intersection or a highway.
Everything else is a place.

## Key decisions

- **Road traffic belongs to the road, not to the landmark.**
  The log names a business as the location of a traffic stop on the road beside it.
  A place's count leaves traffic out, and a road's count keeps every call.
  A place's card shows one line with its traffic count, and the map highlights the road.
- **One kind of pin, sized by calls.**
  Places, roads and groups of nearby pins are the same blue circle, so the size is the only signal.
  Size and opacity follow the square root of the calls, capped at 3,000 so the police station does not hide everything else.
- **A cluster looks like a single pin.**
  A group is sized by the calls it holds, and clicking it zooms until the places separate.
- **One file per place, loaded on click.**
  The map needs every pin's position and count at once, and a card needs far more detail for one pin.
- **The category lives in one SQL function.**
  Every query that needs a category calls it, so the traffic prefix list exists once.
  Editing a category list means a new migration that replaces the function.
- **A road is a bare street, an intersection or a highway.**
  The order is: a ", " in the name means a place; else an AI kind of intersection or highway means a road; else a leading house number means a place; else a bare name is a road.
  A named place with no comma, such as "Colburn Park", counts as a road.
  That is rare, and the normalize prompt asks for "Name, Street".
  Pin ids that share a slug get a suffix after "--", which no slug contains, so ids stay unique and keep pointing at the same pin as counts change.
- **A place with only traffic keeps its pin.**
  It is sized and shaded by its traffic calls, its tooltip and card say "traffic calls nearby", and it has no rank.
- **The lists on a card add up.**
  For a place, outcomes and incidents cover the calls at the place itself, with alarms in the outcomes so false alarms show.
  For a street, both cover every call.
  What the top rows leave out is shown as "Other".
- **A place on its street's point gets no pin.**
  Nominatim returns one point for a street, so every place it could not find would stack there.
  `addresses.json` carries `precision`, `street_id` and `hidden` per address.
  A place with `hidden: true` is left out of the pin GeoJSON, and its street's card lists it under "On <street>, exact spot unknown", with its calls, each row opening its own card.
  It stays in `addresses.json`, so counts, ranks, search and the `#<id>` link work as before, and a hidden place's card lights and rings its street.
  A hidden place's calls add to its street pin's size, but not to the "N calls" a tooltip or group shows, which counts only the pins drawn.
  A place with no street pin keeps its pin, and says "Approximate location, somewhere on <street>" on its card and "approximate location" in its tooltip.
  An approximate road or intersection keeps its pin.
- **Plain words, with the log's words on hover.**
  Common incident types and outcomes get a plain label, and the original text shows on hover.
- **The URL carries the selection**, so a card can be shared.
- **Rank is computed in the browser** from `addresses.json`, as the share of places with fewer calls.

## Open questions

- A filter by person name, which depends on the privacy rules for names in the log.
- A mobile layout, probably a bottom sheet over the map.
