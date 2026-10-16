# Report generator: requirements

**Status:** Done
**Created:** 2026-06-10
**Updated:** 2026-10-16

## Introduction

The static frontend reads its data from JSON files in `frontend/web/public/data/`, and CI cannot reach the database to build them.
The operator needs one command that exports the current PostgreSQL data to those files and commits them, so a push deploys fresh data.
Success means a single Rust binary replaces the Python generators and produces the five files the frontend reads.

## Glossary

- **Report generator:** The `report-gen` binary in `tools/report-gen/`.
- **Publish script:** `scripts/generate_report.sh`, which runs the report generator and commits the output.
- **Log entry:** One row in `log_entries`, parsed from the police daily log.
- **Valid log entry:** A log entry with `parse_error = false`.
- **Output directory:** The folder the report generator writes JSON files into.

## Requirements

### Requirement 1: Connect to the database

**User story:** As an operator, I want the generator to use the same connection setting as the rest of the repo, so that I do not configure it twice.

#### Acceptance criteria

1. WHEN the report generator starts, THE report generator SHALL read `DATABASE_URL` from the environment, after loading a `.env` file in the working directory if one exists.
2. IF no `.env` file exists, THEN THE report generator SHALL continue with the environment as it is.
3. IF `DATABASE_URL` is not set, THEN THE report generator SHALL exit with a non-zero status and the message `DATABASE_URL not set`, without writing any file.
4. IF the database connection fails, THEN THE report generator SHALL exit with a non-zero status and print the connection error, without writing any file.

### Requirement 2: Choose where files go

**User story:** As an operator, I want to set the output directory, so that I can test a run without touching the committed data.

#### Acceptance criteria

1. WHERE `--output-dir <path>` is given, THE report generator SHALL write all files into that path.
2. WHERE `--output-dir` is not given, THE report generator SHALL write into `frontend/web/public/data`, relative to the working directory.
3. IF the output directory or any of its parents does not exist, THEN THE report generator SHALL create them before writing.
4. WHEN a file with the same name already exists in the output directory, THE report generator SHALL replace it.
5. THE report generator SHALL write each file as pretty-printed JSON.

### Requirement 3: Export summary stats

**User story:** As a site visitor, I want headline counts for the police log, so that I can see the overall picture at a glance.

#### Acceptance criteria

1. THE report generator SHALL write `stats.json` with the keys `total`, `generated_at`, `by_type`, and `by_weekday`.
2. THE report generator SHALL set `total` to the number of valid log entries.
3. THE report generator SHALL set `generated_at` to the run time in UTC, formatted as RFC 3339.
4. THE report generator SHALL list in `by_type` at most 20 incident types with their counts, highest count first, from valid log entries with a non-null type.
5. THE report generator SHALL list in `by_weekday` one entry per weekday that has at least one valid log entry with a non-null `reported_at`, labeled `Sun` through `Sat` and ordered Sunday first.
6. IF a weekday has no matching log entries, THEN THE report generator SHALL leave that day out of `by_weekday`.
7. IF there are no valid log entries, THEN THE report generator SHALL write `total` as 0 and `by_type` and `by_weekday` as empty arrays.

### Requirement 4: Export recent incidents

**User story:** As a site visitor, I want to browse recent police log entries, so that I can see what happened near me.

#### Acceptance criteria

1. THE report generator SHALL write `incidents.json` as an array of at most 2000 valid log entries.
2. THE report generator SHALL order the entries by `reported_at`, newest first.
3. THE report generator SHALL include for each entry `case_number`, `reported_at`, `call_source`, `incident_type`, `disposition`, `location`, `officer`, `reference_number`, and `source_url`.
4. IF a field is null in the database, THEN THE report generator SHALL write it as JSON `null`.
5. IF there are no valid log entries, THEN THE report generator SHALL write an empty array.

### Requirement 5: Export geocoded addresses

**User story:** As a site visitor, I want incident counts by address on a map, so that I can see where calls cluster.

#### Acceptance criteria

1. THE report generator SHALL write `addresses.json` as an array with one row per distinct log entry location that has a geocoded match in `address_normalizations`.
2. THE report generator SHALL include for each row `raw_address`, `normalized_address`, `count`, `lat`, and `lng`.
3. THE report generator SHALL order the rows by `count`, highest first.
4. IF a location has no match or its match has a null `lat` or `lng`, THEN THE report generator SHALL leave that location out.
5. IF no locations are geocoded, THEN THE report generator SHALL write an empty array.

### Requirement 6: Export city staff

**User story:** As a site visitor, I want a directory of city staff, so that I can find who to contact.

#### Acceptance criteria

1. THE report generator SHALL write `staff.json` as an array of every row in `city_staff`.
2. THE report generator SHALL include for each row `id`, `name`, `title`, `department`, `division`, `email`, `phone`, and `source_url`.
3. THE report generator SHALL order the rows by department, then division, then name.
4. IF `city_staff` is empty, THEN THE report generator SHALL write an empty array.

### Requirement 7: Export properties

**User story:** As a site visitor, I want property assessment data, so that I can look up and compare parcels.

#### Acceptance criteria

1. THE report generator SHALL write `properties.json` as an array of every row in `properties`.
2. THE report generator SHALL include for each row `parcel_id`, `location`, `owner`, `owner_address`, `land_use`, `lot_size_acres`, `year_built`, `building_sqft`, `assessed_land`, `assessed_building`, `assessed_total`, `assessment_year`, and `detail_url`.
3. THE report generator SHALL write `lot_size_acres` as a JSON number, not a string.
4. THE report generator SHALL order the rows by `assessed_total`, highest first, with null totals last.
5. IF `properties` is empty, THEN THE report generator SHALL write an empty array.

### Requirement 8: Report progress and failure

**User story:** As an operator, I want to see what each run produced, so that I can tell a good run from a bad one.

#### Acceptance criteria

1. WHEN the report generator finishes each file, THE report generator SHALL print one line naming the file and its count: total incidents for `stats.json`, rows for the others.
2. THE report generator SHALL produce the files in this order: `stats.json`, `incidents.json`, `addresses.json`, `staff.json`, `properties.json`.
3. IF a query or a file write fails, THEN THE report generator SHALL stop, print the error, and exit with a non-zero status.
4. IF a run stops partway, THEN THE report generator SHALL leave the files it already wrote in place.
5. WHEN all five files are written, THE report generator SHALL exit with status 0.

### Requirement 9: Publish the data

**User story:** As an operator, I want one command that regenerates and commits the data, so that a push deploys it without CI touching the database.

#### Acceptance criteria

1. WHEN the publish script runs, THE publish script SHALL run the report generator in release mode with the output directory set to `frontend/web/public/data` under the repo root.
2. WHEN the report generator succeeds, THE publish script SHALL stage `frontend/web/public/data/`.
3. IF the staged data has no changes, THEN THE publish script SHALL print `(no changes)` and exit with status 0 without committing.
4. WHEN the staged data has changes, THE publish script SHALL commit them with the message `chore: update public data YYYY-MM-DD`, using the UTC date.
5. IF the report generator fails, THEN THE publish script SHALL stop without staging or committing.
6. THE publish script SHALL work from any working directory, by resolving the repo root from its own location.

## Out of scope

- Pushing the commit or deploying. The operator pushes, and CI deploys.
- A live API. The frontend stays static for the MVP.
- Incremental exports. Every run rewrites all five files.
- Filtering parse errors out of `addresses.json` counts. See Open questions in the design.
