"""Back up the MongoDB database that holds the raw source archive.

The mongo_backup DAG runs this daily inside the Airflow image:

    python maintenance/mongo_backup.py

It writes a gzipped mongodump archive to BACKUP_DIR, a bind mount of the host's
~/backups/data-project/mongo, and keeps the 7 newest. Any failure exits non-zero,
so the DAG run shows it failed.
"""

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import logfire
from mongo.client import MongoDB

BACKUP_DIR = Path("/opt/backups/mongo")
KEEP = 7

Runner = Callable[[Sequence[str]], int]


class BackupError(Exception):
    pass


def check_writable(folder: Path) -> None:
    """Fail before mongodump starts when the backup folder cannot take a backup."""
    if not folder.is_dir():
        raise BackupError(
            f"Backup folder {folder} does not exist. Create it on the host first; "
            "see scrapers/README.md."
        )
    if not os.access(folder, os.W_OK):
        raise BackupError(
            f"Backup folder {folder} is not writable by this user. A folder Docker "
            "creates for a bind mount is owned by root; see scrapers/README.md."
        )


def backup_name(database: str, now: datetime) -> str:
    # The timestamp sorts by name, so the newest backups are the last names.
    return f"{database}-{now:%Y%m%dT%H%M%SZ}.archive.gz"


def run_tool(
    tool: str, settings: MongoDB, arguments: Sequence[str], run: Runner
) -> int:
    """Run mongodump or mongorestore against the configured server."""
    # The password goes in a config file, not the command line, so it does not show
    # up in the process list or the Airflow task log.
    with tempfile.NamedTemporaryFile("w", suffix=".yaml") as config:
        os.chmod(config.name, 0o600)
        # JSON quoting is valid YAML, so any password survives.
        config.write(f"password: {json.dumps(settings.password)}\n")
        config.flush()
        return run(
            [
                tool,
                f"--host={settings.host}",
                f"--port={settings.port}",
                f"--username={settings.username}",
                "--authenticationDatabase=admin",
                f"--config={config.name}",
                *arguments,
            ]
        )


def run_mongodump(settings: MongoDB, dest: Path, run: Runner) -> None:
    arguments = [f"--db={settings.default_db}", "--gzip", f"--archive={dest}"]
    returncode = run_tool("mongodump", settings, arguments, run)
    if returncode != 0:
        dest.unlink(missing_ok=True)
        raise BackupError(f"mongodump exited with status {returncode}")


def prune(folder: Path, database: str, keep: int = KEEP) -> list[Path]:
    """Delete all but the newest `keep` backups of the database, and return them."""
    backups = sorted(folder.glob(f"{database}-*.archive.gz"))
    old = backups[:-keep] if len(backups) > keep else []
    for path in old:
        path.unlink()
    return old


def back_up(folder: Path, settings: MongoDB, now: datetime, run: Runner) -> Path:
    check_writable(folder)
    dest = folder / backup_name(settings.default_db, now)
    with logfire.span("back up mongo", database=settings.default_db, dest=str(dest)):
        run_mongodump(settings, dest, run)
    removed = prune(folder, settings.default_db)
    logfire.info(
        "mongo backup written",
        dest=str(dest),
        size_bytes=dest.stat().st_size,
        removed=[path.name for path in removed],
    )
    return dest


def _run(command: Sequence[str]) -> int:
    return subprocess.run(command, check=False).returncode


def main() -> int:
    logfire.configure()
    try:
        dest = back_up(BACKUP_DIR, MongoDB(), datetime.now(UTC), _run)
    except BackupError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Backup written to {dest}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
