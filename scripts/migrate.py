"""Apply every pending database change: the Postgres migrations, then the MongoDB indexes.

    uv run migrate

Both steps are safe to run again. It stops at the first one that fails.
"""

import sys
from collections.abc import Callable
from pathlib import Path


def upgrade_postgres() -> None:
    import postgres
    from alembic import command
    from alembic.config import Config

    # The workspace is installed from its source tree, so alembic.ini sits beside src/.
    alembic_ini = Path(postgres.__file__).resolve().parents[2] / "alembic.ini"
    command.upgrade(Config(alembic_ini), "head")


def create_mongo_indexes() -> None:
    from mongo import init_indexes

    init_indexes()


STEPS: list[tuple[str, Callable[[], None]]] = [
    ("Postgres migrations", upgrade_postgres),
    ("MongoDB indexes", create_mongo_indexes),
]


def main() -> int:
    from dotenv import load_dotenv

    # postgres.client reads POSTGRES_* when it is first imported, so load .env before
    # any step imports it.
    load_dotenv()
    for name, step in STEPS:
        try:
            step()
        except Exception as exc:
            print(f"{name} failed: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
