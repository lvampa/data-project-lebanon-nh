# Postgres backup: design

**Status:** Done
**Created:** 2026-11-13
**Updated:** 2026-11-14

## Overview

A hand-run script dumps the Postgres database to a dated file.
`python -m maintenance.postgres_backup` runs `pg_dump -Fc` once, inside the Airflow image, and writes `app-<UTC timestamp>.dump` to `/opt/backups/postgres`.
That path is a bind mount of the host folder set in `compose.yml` and `.env.example`.

## How it works

- The password goes in a temporary `PGPASSFILE`, never in the command line or the file name.
- It dumps to `<name>.partial` and renames on success, so a failed or interrupted run leaves no file that looks like a backup.
- A failure raises `BackupError` and exits 1.
  The script reuses `BackupError` and `check_writable` from the Mongo backup.
- `docker/Dockerfile.airflow` installs `postgresql-client-16`, because Debian's version 15 refuses a version 16 server.

## Decisions

- **A dated file per run, no pruning.**
  The operator deletes old files by hand.
  Rejected: a nightly DAG, rotation, a verified single copy, and automatic restore checks.
  They were built and cut as too much for a small hobby project.

## Testing

Unit tests use a fake `pg_dump`.
They cover a new dated file that leaves older ones alone, no password in the command, environment or file name, a failed or interrupted dump leaving no file, a same-second rerun refused, and a missing folder.
