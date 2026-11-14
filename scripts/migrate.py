"""Apply every pending database change, then rebuild the dbt consumer models.

    uv run migrate

The steps are: drop the `marts` views, the Postgres migrations, the MongoDB indexes,
then `dbt build`. Every step is safe to run again. It stops at the first one that fails.
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSFORM_DIR = REPO_ROOT / "transform"


def drop_consumer_models() -> None:
    from postgres.client import engine
    from sqlalchemy import text

    # Postgres won't let a migration drop or retype a column a view reads, so the dbt
    # views go first and are rebuilt by the last step.
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS marts CASCADE"))


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


def build_consumer_models() -> None:
    # Subprocesses, so the scripts package doesn't depend on dbt. dbt reads the
    # POSTGRES_* settings that main() loaded from .env.
    subprocess.run(
        [sys.executable, str(TRANSFORM_DIR / "write_disposition_seed.py")], check=True
    )
    dbt = Path(sys.executable).parent / "dbt"
    subprocess.run(
        [str(dbt), "build", "--project-dir", str(TRANSFORM_DIR),
         "--profiles-dir", str(TRANSFORM_DIR)],
        check=True,
    )  # fmt: skip


STEPS: list[tuple[str, Callable[[], None]]] = [
    ("Dropping the consumer models", drop_consumer_models),
    ("Postgres migrations", upgrade_postgres),
    ("MongoDB indexes", create_mongo_indexes),
    ("Consumer models (dbt build)", build_consumer_models),
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
