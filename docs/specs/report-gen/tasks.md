# Report generator: tasks

**Status:** Done
**Created:** 2026-06-10
**Updated:** 2026-10-16

- [x] 1. Scaffold the workspace and CLI
  - Add the root `Cargo.toml` workspace and the `tools/report-gen` crate with its dependencies.
  - Add `main.rs` with the `--output-dir` argument, `.env` loading, the `DATABASE_URL` check, and the pool connection.
  - Set `#![deny(clippy::all, clippy::pedantic)]`.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2_

- [x] 2. Add the output module
  - Add `write_json`, which creates the directory, pretty-prints, and replaces the file.
  - Test that content round-trips and that missing nested directories are created.
  - _Requirements: 2.3, 2.4, 2.5_

- [x] 3. Add the database module and wire it into `main`
  - [x] 3.1 Add `fetch_stats` with the total, top-20 by type, and by-weekday queries.
  - [x] 3.2 Add `fetch_incidents` with the 2000-row limit.
  - [x] 3.3 Add `fetch_addresses`, limited to geocoded locations.
  - [x] 3.4 Add `fetch_staff`.
  - [x] 3.5 Add `fetch_properties`, casting `lot_size_acres` to `FLOAT8`.
  - [x] 3.6 Call all five in order from `main`, printing one line per file.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 4. Pass the lint gate
  - Run `cargo fmt --check` and `cargo clippy -p report-gen -- -D warnings`, and fix what they report.
  - _Requirements: none (code quality)_

- [x] 5. Point the publish script at the Rust binary
  - Replace the `uv run python` call in `scripts/generate_report.sh` with `cargo run -p report-gen --release -- --output-dir "$REPO_ROOT/frontend/web/public/data"`.
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

- [x] 6. Smoke test against the local database
  - Run the binary into a temp directory and check the five files and their top-level keys.
  - Run the full publish script.
  - _Requirements: 3.1, 4.3, 5.2, 8.1, 9.4_

- [x] 7. Cast `EXTRACT(DOW)` to `FLOAT8`
  - PostgreSQL 14 and later return `NUMERIC`, which does not decode into `f64`.
  - _Requirements: 3.5_

- [x] 8. Remove the superseded Python generators
  - Delete `scrapers/scripts/generate_report.py`, `scripts/generate/generate_web_data.py`, their tests, and the stale root `deploy.sh`.
  - _Requirements: 9.1_
