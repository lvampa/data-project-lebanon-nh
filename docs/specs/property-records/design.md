# Property records: design

**Status:** Approved
**Created:** 2026-11-18
**Updated:** 2026-11-18

## What it is

The town's assessor publishes every parcel on VGSI.
We crawl it monthly, keep every page in the raw archive, and build the `properties` and `property_sales` tables from the archive.
Properties are the hub that other sources join to: police log locations today, building permits and other town records later.

## Data flow

```
crawl (monthly)  VGSI letters -> streets -> parcels -> raw_sources (MongoDB)
                 records one crawl_runs row: started_at, finished_at, pages
build            newest archived page per parcel seen in the latest finished crawl
                 -> parse -> quality checks -> replace properties + property_sales in one transaction
llc lookup       distinct owners matching the business pattern -> llcs -> NH Secretary of State
export           public_properties view -> properties.json
```

The crawl fetches and archives only.
It parses nothing and writes no property rows, so a parser bug never needs a recrawl.

`build` is the only writer of `properties` and `property_sales`.
It reads the archive locally, so a full build takes about a minute, and the operator runs it again after any parser fix.

## Key decisions

- **Extract and transform are separate steps.**
  Rejected: parsing during the crawl with a replay command as a second writer.
  Two writers needed a clock swap, a grace window and a skip for newer rows to avoid overwriting each other.
- **Full rebuild, not upserts.**
  The town has a few thousand parcels, so truncate and insert in one transaction is fast and always correct.
  Readers never see half a build.
- **Build from the latest crawl only.**
  A parcel the town merged or split drops out on the next build.
- **The parcel key is the MBLU (map, block, lot).**
  It is the town's own identifier and the one other town records use, such as building permits.
  `vgsi_pid` is kept only to fetch the page, since VGSI can renumber it.
  Joins between tables still use the surrogate `id`; joins to other sources use `mblu`.
- **Lineage on every row.**
  Each row records `crawl_run_id` and `fetched_at`, the time the archive last saw its page.
- **Quality checks gate the build.**
  The first real crawl stored 161 parcels on A streets only, with 9 empty fields and no sales, and reported success.
  The build now fails and keeps the old tables when a check fails.
- **The LLC job finds its own work.**
  It selects distinct owners matching the business pattern from `properties`.
  The crawl no longer queues LLCs, and `property_llcs` is dropped; an LLC joins to its parcels on the normalized owner name.
- **Value history is not a separate table.**
  Each parcel page carries its own assessment history, stored as `value_history` JSON.
- **Publish through a view.**
  We collect every field on the page.
  The export reads `public_properties`, a view that lists the published columns, so a new raw column never reaches the site by accident.

## Quality checks

The build fails, logs an error and exits non-zero when any of these is true.

| Check | Fails when |
|---|---|
| Parcel count | Below the floor on the first build, or more than 10% away from the current table |
| Core fields | `location`, `owner`, `mblu` or `assessed_total` is empty on more than 5% of parcels |
| Key | Two parcels share an `mblu` |
| Sales | Fewer than half of parcels have a sale |

The thresholds are constants in one place, to be tuned after the first full build.

## Schedule

Airflow runs the crawl monthly, then the build, then the LLC lookup.
Assessments change once a year, so sales lag by at most a month.

## Open questions

- Whether `owner_address` stays in `public_properties`.
  It is published today, and the view keeps today's columns until that is decided.
