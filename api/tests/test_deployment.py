from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FILES = [*REPO_ROOT.glob("compose*.yml"), *REPO_ROOT.glob("docker/Dockerfile*")]


def _uvicorn_lines() -> list[tuple[str, str]]:
    return [
        (path.name, line.strip())
        for path in FILES
        for line in path.read_text().splitlines()
        if "uvicorn" in line
    ]


def test_the_api_is_started_somewhere():
    assert _uvicorn_lines()


@pytest.mark.parametrize(("name", "line"), _uvicorn_lines())
def test_uvicorn_starts_the_app_factory(name, line):
    # api.main has no module-level app, so `api.main:app` would fail to start.
    assert '"--factory", "api.main:create_app"' in line
