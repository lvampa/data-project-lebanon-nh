from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FILES = [REPO_ROOT / "compose.yml", *REPO_ROOT.glob("docker/Dockerfile*")]


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


SHARED_PACKAGES = sorted(
    pyproject.parent.name
    for pyproject in (REPO_ROOT / "shared").glob("*/pyproject.toml")
)
IMAGES = ["Dockerfile.api", "Dockerfile.airflow"]


@pytest.mark.parametrize("image", IMAGES)
@pytest.mark.parametrize("package", SHARED_PACKAGES)
def test_every_shared_package_is_copied_into_the_image(image, package):
    # `uv sync --frozen` fails on a workspace dependency whose folder is missing.
    dockerfile = (REPO_ROOT / "docker" / image).read_text()

    assert f"shared/{package} ./shared/{package}/" in dockerfile
