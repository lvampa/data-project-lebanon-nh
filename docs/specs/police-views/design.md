# Police views: design

**Status:** Draft
**Created:** 2026-11-21
**Updated:** 2026-11-21

## What it is

The police map page gets four views of the same year of police activity, as tabs: Map, Places, Busy times and Officers.
One filter bar above them narrows every view by the kind of activity, the time of day and the dates.
The Map is today's map, unchanged in style, with counts that follow the filters.
Places ranks the places police were called to most.
Busy times shows when police are busiest, week by week, and how long they stay.
Officers shows who handled the activity.
The prototype is `tmp/ux/views.html`, which is untracked.

## Data flow

```
places.sql (one query, as today)
  └─ new column: entries, every log entry of the pin, as a JSON array
report-gen
  ├─ addresses.json, places/<id>.json, stats.json   as today
  └─ activity.json   one row per entry, in columns, with lookup tables
frontend/web /map
  ├─ loads addresses.json and stats.json at build time, as today
  └─ fetches /data/activity.json the first time a filter or another tab is used
```

```jsonc
// activity.json. Every column has one value per entry, in the same order.
{
  "since": "2026-01-01",
  "pins": ["lebanon-ford-90-miracle-mile", "..."],     // ids from addresses.json
  "lookups": {
    "category": ["premises", "traffic", "alarms", "checks", "admin"],
    "type": ["Welfare Check", "..."],
    "disposition": ["Log Information", "..."],
    "source": ["Initiated", "Telephone", "..."],
    "officer": ["...", null]
  },
  "columns": {
    "pin": [0, 0, 1],          // index into pins
    "minute": [7920, 8040],    // minutes from `since` at midnight, New Hampshire time
    "category": [0, 2],        // index into lookups.category, and so on
    "type": [], "disposition": [], "source": [], "officer": [],
    "response": [6, -1],       // minutes from dispatch to arrival, -1 when not timed
    "scene": [14, -1]          // minutes from arrival to clearing, -1 when not timed
  }
}
```

`minute` is wall-clock minutes: the log's own local time, with no zone, minus `since` at midnight, so a daylight saving change never shifts an entry.
An entry with no report time is placed at its log day's midnight.
With the dev data, 23,850 entries, it is 725 KB, and 186 KB gzipped.

**What the file adds.**
It holds no case numbers or links, and no address text beyond the pin ids, which are slugs of the normalized address.
But it is a minute-level timeline of every entry at every pin for the year, where a card shows only a pin's top types and latest ten calls.
House-level data was accepted on 2026-11-14.
When person-named locations are hidden on the public site, the same rule must scrub `pins` here as well as `addresses.json`.
It also names the officer on every entry, where `incidents.json` holds only the latest 2,000.

## Key decisions

- **Entries come from `places.sql`, not a second query.**
  The pin ids are worked out once, so an entry can never point at a pin the map does not have.
  A second query would copy the pin and slug rules and drift.
- **Response and scene times are worked out in report-gen**, in two pure functions with unit tests.
  Response runs from dispatch, or the log time when there is no dispatch, to arrival.
  It is left out for entries an officer started and for walk-ins, which are already at the station.
  Scene runs from arrival, or the log time for an entry an officer started, to clearing.
  Over 10 hours is a log slip and is left out.
- **The default map needs no new data.**
  With the default filters, the counts are the ones in `addresses.json`, so the page loads as fast as today.
  `activity.json` loads the first time someone changes a filter or opens another tab.
- **The map's style does not change.**
  Filtered counts go into the live map as `Address` rows with new `count` and `traffic_count`, so pins, groups, hidden places and "traffic nearby" keep working as they do.
  `traffic_count` counts only kept traffic, so under "About a place" or "Alarms" it is 0 and no place turns into "traffic nearby".
  A pin a filter empties leaves the map, unless hidden places with activity ride on it.
  The map updates its pin source in place instead of being rebuilt on every change.
  The selection, the hash and the search keep the year's rows, so a filter change never flies the map, and a card hides its rank while filters are on.
- **One kind at a time:** All activity, About a place, Traffic and Alarms.
  "All activity" keeps the map's rule that traffic counts on the road, not the business beside it.
  With Traffic chosen, a place shows its traffic as "traffic stops and calls nearby", as today.
- **"Activity" and "log entries", not "calls".**
  Officers start about half the entries themselves, such as patrols, checks and stops.
  "Calls" is kept for calls from the public, on Places and for the time to arrive.
- **Places has one fixed lens: calls from the public about something at a place.**
  That is the "about a place" kind, started by a caller, at a place and not a road.
  False alarms are shown apart on each card and are never in the rank.
  The police station is left out, because the log files reports taken at the station there, not where they happened.
  It is matched by its pin id, so a rename of its normalized address would bring it back; that is a known risk.
  Its count was 1,217, made of 602 walk-ins and 615 calls.
  The kind chips step aside on this tab.
- **No trend and no speed ranking.**
  The map spec says the card adds no commentary and no trend, so Places has no "rising lately" sort.
  Only about a third of entries have an arrival time, so nothing ranks places or officers by response.
  The time to arrive appears only on a place's card, with how many timed calls it rests on.
- **Busy times describes a pattern, not a record.**
  The heat map's finding names the busiest three-hour stretch, on weekdays or weekends, and the quietest.
  The weekly finding gives a typical week and whether the year was steady.
  "How long police stay" shows the typical minutes on scene for the most common types, as bars.
  Paid details and paperwork are left out of it, because a detail is a shift and paperwork is not a visit.
- **Incomplete weeks are striped, not faded.**
  A week with under half the typical activity is missing logs, and the current week is still filling in.
  Neither counts as the busiest week.
- **Officers are shown descriptively.**
  A card shows the officer's entries, how many they started themselves, the hours they work, what they handle most and their typical time on scene.
  The only sorts are most entries and A to Z.
  Entries with no officer, about a fifth, are left out and the page says how many.
  "See on the map" filters every tab to that officer.
- **The view and filters live in the URL query, and the selected pin stays in the hash**, so a filtered view can be shared.
- **One chart tooltip**, styled like the map's tooltip, opens on hover with a mouse and on tap on a phone.
  The log's text is only ever rendered as text, in the tooltip and everywhere else, never as HTML.
- **Color meets WCAG AA**, checked with computed ratios.
  Hour strips and the heat map use steps from the sequential scale that each reach 3:1, with the scale reversed in the dark theme.
  The weekly chart labels each series directly and separates segments with a 1px gap.
  The map pins' lowest opacity rises from .45 to .65, the lowest that reaches 3:1 on the basemap.
  The `--input` border token darkens to reach 3:1, which also darkens every input on the site.

## Also in this change

- One click on a group of pins zooms until every place in it shows, instead of only to where the group first splits.
- The nav and the footer mark Voter Info, Properties and Government "Coming soon" with a small chip.
- The footer's top edge fades from the page into the brand color.
- On the map page, the map is full width and fills the window under the tabs and filters.

## Open questions

- Whether a caller's alarm that turns out real counts as a call from the public about the place.
  Today no alarm counts.
- Whether the Officers tab goes public with this change, since an officer's hours and time on scene sit close to a performance view.
  It also decides whether `activity.json` carries the officer column.
- Under narrow filters most pins drop to the smallest size, because the size scale is tuned to a year of all activity.
