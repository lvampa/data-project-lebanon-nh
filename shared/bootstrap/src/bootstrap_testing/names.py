"""Test database names that differ between checkouts.

Two worktrees running tests at once, or one on an older branch, must not share a
database: a migration from one breaks the other, and a test that clears a collection
breaks a run in the other.
"""

import hashlib
import re
import subprocess
from pathlib import Path

# Postgres cuts identifiers longer than this.
MAX_NAME_LENGTH = 63


def checkout_database_name(prefix: str, checkout: str | None = None) -> str:
    """`<prefix>_<checkout folder>_test`, such as `app_my_worktree_test`."""
    folder = checkout if checkout is not None else _checkout_folder()
    slug = re.sub(r"[^a-z0-9]+", "_", folder.lower()).strip("_") or "checkout"
    name = f"{prefix}_{slug}_test"
    if len(name) <= MAX_NAME_LENGTH:
        return name
    # Cut the folder name, and add a hash of the whole of it so two long names that
    # start alike stay apart.
    digest = hashlib.sha256(slug.encode()).hexdigest()[:8]
    room = MAX_NAME_LENGTH - len(f"{prefix}__{digest}_test")
    return f"{prefix}_{slug[:room]}_{digest}_test"


def _checkout_folder() -> str:
    here = Path(__file__).resolve().parent
    try:
        toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=here,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return Path.cwd().name
    return Path(toplevel).name
