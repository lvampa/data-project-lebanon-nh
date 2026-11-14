"""Back up the PostgreSQL database.

Run it by hand inside the Airflow image:

    python -m maintenance.postgres_backup

It writes a new `pg_dump -Fc` file to BACKUP_DIR, a bind mount of the host's
~/backups/data-project/postgres, every time. Nothing is overwritten or deleted, so
clear out old ones by hand. It writes to a .partial file and renames it only on
success, so a failed or interrupted run leaves no file that looks like a backup.
"""

import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import logfire
from sqlalchemy import URL

from maintenance.mongo_backup import BackupError, check_writable

BACKUP_DIR = Path("/opt/backups/postgres")

# Runs a command with extra environment variables and returns its exit status.
Runner = Callable[[Sequence[str], Mapping[str, str]], int]


def backup_name(database: str, now: datetime) -> str:
    # The timestamp sorts by name, so the newest backups are the last names.
    return f"{database}-{now:%Y%m%dT%H%M%SZ}.dump"


def pgpass_line(url: URL) -> str:
    """One .pgpass line for the server; the database field is a wildcard."""

    def escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace(":", "\\:")

    fields = [url.host or "", str(url.port or 5432), "*", url.username or ""]
    fields.append(url.password or "")
    return ":".join(escape(field) for field in fields) + "\n"


def run_pg_dump(url: URL, dest: Path, run: Runner) -> None:
    # The password goes in a PGPASSFILE, not the command line, so it does not show
    # up in the process list or the Airflow task log. The file is created mode 0600.
    with tempfile.NamedTemporaryFile("w", suffix=".pgpass") as passfile:
        passfile.write(pgpass_line(url))
        passfile.flush()
        returncode = run(
            [
                "pg_dump",
                "-Fc",
                f"--host={url.host}",
                f"--port={url.port or 5432}",
                f"--username={url.username}",
                f"--file={dest}",
                str(url.database),
            ],
            {"PGPASSFILE": passfile.name},
        )
    if returncode != 0:
        raise BackupError(f"pg_dump exited with status {returncode}")


def back_up(folder: Path, url: URL, now: datetime, run: Runner) -> Path:
    check_writable(folder)
    dest = folder / backup_name(str(url.database), now)
    if dest.exists():
        raise BackupError(f"{dest} already exists; wait a second and run it again.")
    # A half-written file must never carry a backup name, even if the run is killed.
    partial = dest.with_name(dest.name + ".partial")
    try:
        with logfire.span("back up postgres", database=url.database, dest=str(dest)):
            run_pg_dump(url, partial, run)
        os.replace(partial, dest)
    finally:
        partial.unlink(missing_ok=True)
    logfire.info(
        "postgres backup written", dest=str(dest), size_bytes=dest.stat().st_size
    )
    return dest


def _run(command: Sequence[str], env: Mapping[str, str]) -> int:
    return subprocess.run(command, check=False, env={**os.environ, **env}).returncode


def main() -> int:
    from postgres.client import engine

    logfire.configure()
    try:
        dest = back_up(BACKUP_DIR, engine.url, datetime.now(UTC), _run)
    except BackupError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Backup written to {dest}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
