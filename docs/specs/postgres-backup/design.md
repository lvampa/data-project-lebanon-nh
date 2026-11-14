# Postgres backup: design

**Status:** In progress
**Created:** 2026-11-13
**Updated:** 2026-11-13

## Overview

`scrapers/maintenance/postgres_backup.py` runs `pg_dump -Fc` once, by hand, inside the Airflow image: `python -m maintenance.postgres_backup`.
It covers requirement 1.

- The file is `app-20261113T221000Z.dump`, in `/opt/backups/postgres`, a bind mount of the host folder set in `compose.yml` and `.env.example`.
- The password goes in a temporary `PGPASSFILE`, passed to `pg_dump` in its environment (1.5).
- It dumps to `<name>.partial` and renames it on success, so a failed or Ctrl-C'd run leaves no backup-looking file; a failure raises `BackupError` and `main` exits 1 (1.4).
- It reuses `BackupError` and `check_writable` from `mongo_backup` (1.3), so it runs as a module.
- `docker/Dockerfile.airflow` installs `postgresql-client-16`, because Debian's version 15 refuses a version 16 server.

## Decisions

- **A dated file per run, no pruning.**
  Connor's choice for a small hobby project.
  Rejected: a nightly DAG, rotation, a verified single copy, and automatic restore checks.
  They were built and cut as too much for the app.

## Testing strategy

- Unit tests with a fake `pg_dump`: a new dated file that leaves older ones alone, no password in the command, environment or file name, a failed or interrupted dump leaving no file, a same-second rerun refused, and a missing folder.
