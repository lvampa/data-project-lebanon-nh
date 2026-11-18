import subprocess
import sys

IMPORT_THEN_SET_ENV = """
import os
import postgres, postgres.models
from postgres.client import get_engine

assert get_engine.cache_info().currsize == 0
os.environ["POSTGRES_DB"] = "set_after_import"
assert get_engine().url.database == "set_after_import"
"""


def test_importing_postgres_builds_no_engine_and_reads_settings_late():
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_THEN_SET_ENV],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
