"""A bare `pytest` from the repo root must not depend on `.env` being readable.

pytest asks about every entry in the folder it collects from, `.env` included, and
stopped with a PermissionError when the file could not be read. Nothing in the repo
reads `.env` during collection; the fix is in the root pytest config.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Makes every path whose name starts with `.env` fail to stat, as it does where the
# file is unreadable, without needing a real unreadable file.
UNREADABLE_ENV_PLUGIN = """
import os

_real_stat = os.stat


def _stat(path, *args, **kwargs):
    if os.path.basename(os.fspath(path)).startswith(".env"):
        raise PermissionError(1, "Operation not permitted", os.fspath(path))
    return _real_stat(path, *args, **kwargs)


os.stat = _stat
"""


@pytest.mark.parametrize("env_file", [".env", ".env.local"])
def test_collection_works_when_an_env_file_is_unreadable(tmp_path, env_file):
    project = tmp_path / "project"
    (project / "tests").mkdir(parents=True)
    # The repo's own pytest config, applied to a folder that has a `.env` in it.
    shutil.copy(REPO_ROOT / "pyproject.toml", project / "pyproject.toml")
    (project / env_file).write_text("SECRET=1\n")
    (project / "tests" / "test_one.py").write_text("def test_one():\n    pass\n")
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "unreadable_env.py").write_text(UNREADABLE_ENV_PLUGIN)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "unreadable_env",
        ],
        cwd=project,
        env={**os.environ, "PYTHONPATH": str(plugins)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert "1 test collected" in result.stdout, result.stdout + result.stderr
    assert result.returncode == 0
