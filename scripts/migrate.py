"""Apply every pending database change: the Postgres migrations, then the MongoDB indexes.

    uv run migrate

Both steps are safe to run again. It stops at the first one that fails.
"""

import sys
from collections.abc import Callable
from pathlib import Path

import postgres
from alembic import command
from alembic.config import Config
from bootstrap import bootstrap
from mongo import init_indexes


def upgrade_postgres() -> None:
    # The workspace is installed from its source tree, so alembic.ini sits beside src/.
    alembic_ini = Path(postgres.__file__).resolve().parents[2] / "alembic.ini"
    command.upgrade(Config(alembic_ini), "head")


def create_mongo_indexes() -> None:
    init_indexes()


STEPS: list[tuple[str, Callable[[], None]]] = [
    ("Postgres migrations", upgrade_postgres),
    ("MongoDB indexes", create_mongo_indexes),
]


def main() -> int:
    bootstrap("migrate")
    for name, step in STEPS:
        try:
            step()
        except Exception as exc:
            print(f"{name} failed: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
