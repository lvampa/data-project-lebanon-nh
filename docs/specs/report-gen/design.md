# Report generator: design

**Status:** Done
**Created:** 2026-06-10
**Updated:** 2026-10-16

## Overview

A single Rust binary, `report-gen`, connects to PostgreSQL, runs five read-only queries, and writes one JSON file per query into the output directory.
`scripts/generate_report.sh` runs it in release mode and commits the result, so CI can deploy static data without database access.
It replaced `scrapers/scripts/generate_report.py` and `scripts/generate/generate_web_data.py`, which were deleted on 2026-09-07.
This covers requirements 1 through 9.

## Architecture

```
scripts/generate_report.sh
  └─ cargo run -p report-gen --release -- --output-dir <repo>/frontend/web/public/data
       main.rs   parse args, load .env, connect pool
         ├─ db::fetch_stats       → output::write_json("stats.json")
         ├─ db::fetch_incidents   → output::write_json("incidents.json")
         ├─ db::fetch_addresses   → output::write_json("addresses.json")
         ├─ db::fetch_staff       → output::write_json("staff.json")
         └─ db::fetch_properties  → output::write_json("properties.json")
  └─ git add frontend/web/public/data/ && git commit (only if changed)
```

Each query runs and its file is written before the next query starts.

## Components and interfaces

### Cargo workspace

`Cargo.toml` at the repo root declares a workspace with the single member `tools/report-gen`, resolver 2.
The crate uses Rust 2024 edition.

Dependencies: `sqlx` 0.8 (`runtime-tokio`, `postgres`, `chrono`), `tokio` (`full`), `serde`, `serde_json`, `chrono` (`serde`), `clap` 4 (`derive`), `dotenvy`, and `anyhow`.
`tempfile` is a dev-dependency.

### CLI (`tools/report-gen/src/main.rs`)

```
report-gen [--output-dir <PATH>]

  --output-dir <PATH>   Output directory for JSON files
                        [default: frontend/web/public/data]
```

Environment: `DATABASE_URL`, loaded from `.env` by `dotenvy` if the file exists.

Stdout on success:

```
✓ stats.json  (N total incidents)
✓ incidents.json  (N rows)
✓ addresses.json  (N rows)
✓ staff.json  (N rows)
✓ properties.json  (N rows)
```

`main` returns `anyhow::Result<()>`, so any error prints and exits with status 1.

### Database module (`tools/report-gen/src/db.rs`)

```rust
pub async fn fetch_stats(pool: &PgPool) -> Result<Stats>;
pub async fn fetch_incidents(pool: &PgPool) -> Result<Vec<Incident>>;
pub async fn fetch_addresses(pool: &PgPool) -> Result<Vec<Address>>;
pub async fn fetch_staff(pool: &PgPool) -> Result<Vec<Staff>>;
pub async fn fetch_properties(pool: &PgPool) -> Result<Vec<Property>>;
```

Queries use runtime `sqlx::query_as` and `sqlx::query_scalar`, not the compile-time macros, so building does not need a live database.
`fetch_stats` runs three queries (total, by type, by weekday) and assembles `Stats` by hand, since it cannot derive `FromRow`.

| Function | Source | Filter | Order | Limit |
|---|---|---|---|---|
| `fetch_stats` total | `log_entries` | `parse_error = false` | - | - |
| `fetch_stats` by type | `log_entries` | valid, `incident_type IS NOT NULL` | count desc | 20 |
| `fetch_stats` by weekday | `log_entries` | valid, `reported_at IS NOT NULL` | DOW asc | - |
| `fetch_incidents` | `log_entries` | valid | `reported_at DESC` | 2000 |
| `fetch_addresses` | `log_entries` join `address_normalizations` on `location = raw_address` | location, lat, lng not null | count desc | - |
| `fetch_staff` | `city_staff` | - | department, division, name | - |
| `fetch_properties` | `properties` | - | `assessed_total DESC NULLS LAST` | - |

### Output module (`tools/report-gen/src/output.rs`)

```rust
pub fn write_json<T: Serialize>(dir: &Path, filename: &str, data: &T) -> Result<()>;
```

Creates `dir` and its parents, serializes `data` with `serde_json::to_string_pretty`, and writes `dir/filename`, replacing any existing file.

### Publish script (`scripts/generate_report.sh`)

Runs with `set -e`.
Resolves `REPO_ROOT` from the script's own location and `cd`s there, so `.env` and the workspace are found.
Runs the binary, stages `frontend/web/public/data/`, and commits only if `git diff --cached --quiet` reports changes.

## Data models

### Postgres to Rust type mapping

| Postgres | Rust | Note |
|---|---|---|
| `TEXT` | `Option<String>` | |
| `TIMESTAMP` | `Option<chrono::NaiveDateTime>` | Serialized without a time zone, like `2026-06-01T14:30:00`. |
| `INTEGER` | `Option<i32>` (`i32` for `city_staff.id`) | |
| `NUMERIC(10,4)` | `Option<f64>` | Cast with `::FLOAT8` in SQL so it serializes as a number. |
| `FLOAT8` | `Option<f64>` | `lat`, `lng`. |
| `COUNT(*)` | `i64` | |
| `EXTRACT(DOW ...)` | `f64` | Cast with `::FLOAT8`, then indexes `["Sun", ..., "Sat"]`. |

### Key types

```rust
pub struct Stats {
    pub total: i64,
    pub generated_at: String,      // RFC 3339, UTC
    pub by_type: Vec<ByType>,
    pub by_weekday: Vec<ByWeekday>,
}
pub struct ByType { pub incident_type: Option<String>, pub count: i64 }
pub struct ByWeekday { pub day: String, pub count: i64 }

pub struct Incident {
    pub case_number: Option<String>,
    pub reported_at: Option<NaiveDateTime>,
    pub call_source: Option<String>,
    pub incident_type: Option<String>,
    pub disposition: Option<String>,
    pub location: Option<String>,
    pub officer: Option<String>,
    pub reference_number: Option<String>,
    pub source_url: Option<String>,
}

pub struct Address {
    pub raw_address: Option<String>,
    pub normalized_address: Option<String>,
    pub count: i64,
    pub lat: Option<f64>,
    pub lng: Option<f64>,
}

pub struct Staff {
    pub id: i32,
    pub name: Option<String>,
    pub title: Option<String>,
    pub department: Option<String>,
    pub division: Option<String>,
    pub email: Option<String>,
    pub phone: Option<String>,
    pub source_url: Option<String>,
}

pub struct Property {
    pub parcel_id: Option<String>,
    pub location: Option<String>,
    pub owner: Option<String>,
    pub owner_address: Option<String>,
    pub land_use: Option<String>,
    pub lot_size_acres: Option<f64>,
    pub year_built: Option<i32>,
    pub building_sqft: Option<i32>,
    pub assessed_land: Option<i32>,
    pub assessed_building: Option<i32>,
    pub assessed_total: Option<i32>,
    pub assessment_year: Option<i32>,
    pub detail_url: Option<String>,
}
```

All types derive `Debug` and `Serialize`; the row types also derive `sqlx::FromRow`.

### Output files

All files are pretty-printed JSON in the output directory.

| File | Shape | Example |
|---|---|---|
| `stats.json` | object | `{"total": 1234, "generated_at": "2026-10-16T12:00:00.123456789+00:00", "by_type": [{"incident_type": "Motor Vehicle Stop", "count": 210}], "by_weekday": [{"day": "Sun", "count": 150}]}` |
| `incidents.json` | array of `Incident` | `[{"case_number": "26-1234", "reported_at": "2026-10-15T08:12:00", ...}]` |
| `addresses.json` | array of `Address` | `[{"raw_address": "MAIN ST", "normalized_address": "Main St, Lebanon, NH", "count": 40, "lat": 43.64, "lng": -72.25}]` |
| `staff.json` | array of `Staff` | `[{"id": 1, "name": "...", "department": "...", ...}]` |
| `properties.json` | array of `Property` | `[{"parcel_id": "...", "lot_size_acres": 0.25, "assessed_total": 350000, ...}]` |

Null database values serialize as JSON `null`.

## Error handling

| Failure | Result |
|---|---|
| `.env` missing | Ignored; the process environment is used. |
| `DATABASE_URL` unset | Exits 1 with `DATABASE_URL not set`; nothing written. |
| Connection fails | Exits 1 with the `sqlx` error; nothing written. |
| A query fails | Exits 1 with the `sqlx` error; files from earlier steps stay on disk. |
| A file write fails | Exits 1 with the I/O error; files from earlier steps stay on disk. |
| Report generator exits non-zero | `set -e` stops the publish script before `git add`. |
| No data changes | The publish script prints `(no changes)` and exits 0. |

Writes are not atomic.
A run that fails partway can leave a mix of new and old files in the output directory, but the publish script never commits that state.

## Testing strategy

- **Unit:** `output.rs` has two tests, using `tempfile`: one checks the written content round-trips, one checks that missing nested directories are created.
- **Lint gate:** `main.rs` sets `#![deny(clippy::all, clippy::pedantic)]`, and `cargo clippy -p report-gen -- -D warnings` and `cargo fmt --check` must pass.
- **Smoke test:** Run `cargo run -p report-gen -- --output-dir <tmp>` against the local database, check the five files and their top-level keys, then run the publish script.
- **Not tested:** The SQL queries and the type mapping have no automated tests, because they need a live Postgres with the schema.
  A type mismatch shows up only at run time, as it did with `EXTRACT(DOW)`.

## Decisions

- **Rust binary over the Python script.**
  The Python generators needed the `uv` environment and duplicated each other.
  Rejected: keeping Python.
  The Rust tool is also a portfolio piece.
- **Runtime queries, not `sqlx::query!` macros.**
  The macros need `DATABASE_URL` or an offline cache at build time.
  Runtime queries build anywhere, at the cost of catching type mismatches only when run.
- **Write each file right after its query.**
  It is simple and keeps memory low.
  Rejected: fetch everything first, then write all files, which would avoid partial output but was not worth it since the publish script does not commit failed runs.
- **Divergence: five files, not two.**
  The plan's goal and Task 1 skeleton described `summary.json` and `incidents.json`, from `fetch_summary` and `fetch_incidents`.
  Before the db module was written, the target moved to match `scripts/generate/generate_web_data.py`, so the built tool writes `stats.json`, `incidents.json`, `addresses.json`, `staff.json`, and `properties.json`.
  The summary type is `Stats` with a `total` field, not `total_incidents`.
- **Divergence: `EXTRACT(DOW)` is cast to `FLOAT8`.**
  The plan assumed `EXTRACT` returns `FLOAT8`.
  On PostgreSQL 14 and later it returns `NUMERIC`, which fails to decode into `f64`, so the query adds `::FLOAT8` (commit `f009927`).
- **Divergence: lint fixes beyond the plan.**
  Clippy pedantic required plain `r"..."` raw strings instead of `r#"..."#`, and `#[allow(clippy::struct_field_names)]` on `ByType`, `Incident`, and `Address`.
- **Divergence: the old generators were deleted.**
  The plan only swapped the call in the publish script.
  Commit `d7262dc` (2026-09-07) later removed `scrapers/scripts/generate_report.py`, `scripts/generate/generate_web_data.py`, their tests, and a stale root `deploy.sh`.
- **Divergence: stdout for `stats.json` prints before the write.**
  The plan printed after writing the summary; the built code prints the line, then writes.
  A failed write therefore follows a success line for that file.

## Open questions

- `incidents.json` orders by `reported_at DESC`, and Postgres puts nulls first in descending order.
  Should entries with no `reported_at` sort last instead?
- `addresses.json` counts include log entries with `parse_error = true`, unlike every other query.
  Is that intended?
- `generated_at` changes on every run, so after any successful run `stats.json` differs and the publish script's `(no changes)` path never triggers.
  Should the timestamp move out of the diffed data, or should the script ignore it?
- The committed `stats.json` is still a placeholder (`total` 0, empty `generated_at`) from 2026-06-07.
  The publish script has not been run against real data and committed since the Rust tool landed.
