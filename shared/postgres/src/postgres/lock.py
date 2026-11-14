"""One lock for every job that writes police log entries.

The process, reprocess, normalization and geocode jobs all write the police log
tables. Running two together would let an old parse overwrite a new one, or two
jobs spend the same AI calls, so each takes this lock for its whole run, from a
shell as well as from Airflow.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text

# Any fixed number works; it only has to be the same in every job.
_LOCK_KEY = 26_05_11_01


@contextmanager
def police_log_lock(engine: Engine) -> Iterator[bool]:
    """Yield whether this process holds the lock. It is released on exit."""
    # Advisory locks belong to a connection, so this one stays open for the run.
    # Autocommit keeps it out of a transaction: an hour idle in one would hold
    # back vacuum on every table.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": _LOCK_KEY}
        )
        try:
            yield bool(acquired)
        finally:
            if acquired:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY}
                )
