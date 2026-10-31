import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not set; the drift check needs an empty Postgres database",
)
def test_migrations_match_models_and_downgrade_cleanly():
    engine = create_engine(TEST_DATABASE_URL)
    # One transaction, so a failed step rolls the test database back to empty.
    with engine.begin() as connection:
        config = Config(ALEMBIC_INI)
        config.attributes["connection"] = connection

        command.upgrade(config, "head")
        command.check(config)
        command.downgrade(config, "base")
    engine.dispose()
