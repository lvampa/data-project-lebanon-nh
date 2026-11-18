import subprocess
import sys

# Run with no POSTGRES_* variables at all: importing must not read them.
IMPORT_BUILDS_NOTHING = """
import os
for name in list(os.environ):
    if name.startswith("POSTGRES_"):
        del os.environ[name]

import postgres, postgres.models
from postgres.client import get_engine
from postgres.settings import get_postgres_settings

assert get_engine.cache_info().currsize == 0
assert get_postgres_settings.cache_info().currsize == 0
"""


def test_importing_postgres_builds_no_engine_and_reads_no_settings():
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_BUILDS_NOTHING],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
