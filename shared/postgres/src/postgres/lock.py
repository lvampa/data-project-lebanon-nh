"""Advisory locks, one per conflict that two runs of a job would cause.

Row-level safety already comes from transactions, upserts and `FOR UPDATE SKIP LOCKED`,
so a lock is only for a conflict the rows cannot settle. A job takes its lock for its
whole run, from a shell as well as from Airflow, and jobs on different locks run
together:

- POLICE_LOG_PARSE: the process and reprocess jobs. Together they could let an old
  parse overwrite a new one on the same PDF.
- NORMALIZE: two runs would spend the same AI calls.
- GEOCODE: two runs would double the request rate to Nominatim.
"""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text

POLICE_LOG_PARSE = "police_log_parse"
NORMALIZE = "normalize"
GEOCODE = "geocode"


def lock_key(name: str) -> int:
    """The same bigint for a name in every process. Python's hash() is not stable."""
    digest = hashlib.sha256(name.encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


@contextmanager
def advisory_lock(engine: Engine, name: str) -> Iterator[bool]:
    """Yield whether this process holds the lock `name`. It is released on exit."""
    key = lock_key(name)
    # Advisory locks belong to a connection, so this one stays open for the run.
    # Autocommit keeps it out of a transaction: an hour idle in one would hold
    # back vacuum on every table.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
        )
        try:
            yield bool(acquired)
        finally:
            if acquired:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                )
