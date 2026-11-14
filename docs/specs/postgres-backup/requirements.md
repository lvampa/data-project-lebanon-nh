# Postgres backup: requirements

**Status:** In progress
**Created:** 2026-11-13
**Updated:** 2026-11-13

## Introduction

Postgres will soon hold human corrections to normalized addresses, which cannot be rebuilt from the raw archive.
A hand-run script backs it up, the same way the Mongo backup works (raw-source-archive requirement 7).

## Requirements

### Requirement 1: Back up Postgres by hand

**User story:** As Connor, I want a script that dumps Postgres to a file, so that losing the volume does not lose the corrections.

#### Acceptance criteria

1. WHEN the operator runs the script, THE script SHALL write a `pg_dump -Fc` dump of the application database to a new dated file in the backup folder, `~/backups/data-project/postgres` or `POSTGRES_BACKUP_DIR`.
2. THE script SHALL NOT overwrite or delete an existing backup, including one with the same name from the same second.
3. IF the backup folder does not exist or cannot be written, THEN THE script SHALL exit non-zero with an error that names the folder.
4. THE script SHALL write to a `.partial` file and rename it only when `pg_dump` succeeds, so a failed or interrupted run leaves no file named like a backup, and exits non-zero on failure.
5. THE script SHALL pass the password through a mode 0600 password file, and never in the command line, a file name, or a log line.

## Out of scope

- Scheduling, restore checks, and removing old backups.
- Copying backups off the machine.
