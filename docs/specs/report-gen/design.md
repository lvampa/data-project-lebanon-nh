# Report generator: design

**Status:** Done
**Created:** 2026-06-10
**Updated:** 2026-11-19

## Overview

`report-gen` is a Rust binary that connects to PostgreSQL, runs read-only queries, and writes one JSON file for each of five outputs for the static frontend.
The police log queries are files in `tools/report-gen/src/sql/`, which `db.rs` includes.
`scripts/generate_report.sh` runs it in release mode, and `scripts/deploy.sh` runs that script before building and deploying the site.
The output lands in `frontend/web/public/data/`, which is gitignored because it carries names and owner addresses.
It replaced two Python generators.

## Data flow

```
scripts/deploy.sh
  ├─ scripts/generate_report.sh   load .env, derive DATABASE_URL from POSTGRES_* if unset,
  │                               then cargo run -p report-gen --release -- --since 2026-01-01 --output-dir <dir>
  │     stats.json  incidents.json  addresses.json  staff.json  properties.json
  ├─ bun run build                (frontend/web)
  └─ wrangler pages deploy        (frontend/web/out)
```

Each query runs and its file is written before the next starts.
`main` returns `anyhow::Result<()>`, so any error prints and exits 1, and the deploy script stops before building.

## What each file holds

- `stats.json`: total valid incidents, the top 20 incident types, and counts by weekday, with `generated_at` and `since` stamps.
- `incidents.json`: the newest 2,000 valid log entries, ones with no reported time last.
- `addresses.json`: valid log entries joined to `address_normalizations` on `location = raw_address`, with coordinates, for the map.
- `staff.json`: `city_staff` by department, division and name.
- `properties.json`: `properties` by assessed total, highest first.

Valid means `parse_error = false`.
The three police log files only hold entries with a `log_date` on or after `--since`, which defaults to 2026-01-01.
Null database values serialize as JSON `null`; columns that are `NOT NULL`, or that a query filters to non-null, are plain types in Rust so the JSON matches the frontend types.
Timestamps are naive, for example `2026-06-01T14:30:00`.

## Components

- `tools/report-gen/` in a root Cargo workspace (Rust 2024, `sqlx`, `tokio`, `serde`, `clap`, `dotenvy`, `anyhow`).
- `db.rs` has one fetch function per file, using runtime `sqlx::query_as`, not the compile-time macros, so it builds without a database.
- `output.rs` has `write_json`, which creates the directory and writes pretty JSON, replacing any existing file.
- `generate_report.sh` does not touch git.

## Testing

`output.rs` has unit tests for the written content and for creating nested directories.
Clippy pedantic and `cargo fmt --check` gate the code.
The police log queries have Python tests in `shared/postgres/tests/`, which run the same SQL files against the test database.
The staff and properties queries, and the type mapping, have no automated tests, because they need a live Postgres with the schema.
A type mismatch shows up at run time, as it did with `EXTRACT(DOW)`, which returns `NUMERIC` on Postgres 14 and later and needs a `::FLOAT8` cast.

## Decisions

- **Rust binary over the Python scripts.**
  The Python generators needed the `uv` environment and duplicated each other.
  The Rust tool is also a portfolio piece.
- **Runtime queries, not `sqlx::query!` macros.**
  The macros need a live database or an offline cache at build time.
  Runtime queries build anywhere, and catch type mismatches only when run.
- **Write each file right after its query.**
  Rejected: fetching everything first and then writing, which would avoid partial output.
  The deploy script already refuses to build from a failed run.
- **Generated data is not committed.**
  The publish script used to commit the JSON for a CI deploy, but there is no CI deploy, and the files carry names and owner addresses.
  The deploy script regenerates the data right before it builds.
  Rejected: empty placeholder files in git, which would let a build without the exporter ship empty pages.
- **Incidents with no reported time sort last, and the cap is printed.**
  The stdout line shows the row count next to the total, so a run that hits the 2,000 cap says so.
- **Police entries are cut off by a start date, and nothing else is filtered.**
  `--since` filters on `log_date`, which is never null, so an entry with no reported time is kept.
  A public filtering layer was built and parked; see the police log pipeline spec.
