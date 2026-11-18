import ast
import tomllib
from pathlib import Path
from unittest.mock import Mock, call

import bootstrap
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# Entry points that have no `__main__` guard or console script.
OTHER_ENTRY_POINTS = [
    "api/main.py",
    "scrapers/extensions.py",
    "shared/postgres/migrations/env.py",
]
# A hello-world stub, not an entry point.
NOT_ENTRY_POINTS = {"scrapers/main.py"}
SKIPPED_DIRECTORIES = {"tests", "versions", "node_modules"}


def _source_files() -> list[Path]:
    return [
        path
        for path in REPO_ROOT.rglob("*.py")
        if not any(
            part.startswith(".") or part in SKIPPED_DIRECTORIES
            for part in path.relative_to(REPO_ROOT).parts
        )
    ]


def _console_script_files() -> set[str]:
    files = set()
    for pyproject in REPO_ROOT.glob("*/pyproject.toml"):
        scripts = tomllib.loads(pyproject.read_text()).get("project", {}).get("scripts")
        for target in (scripts or {}).values():
            module = target.split(":")[0]
            files.add(f"{module.replace('.', '/')}.py")
    return files


def _entry_point_files() -> list[str]:
    with_main_guard = {
        str(path.relative_to(REPO_ROOT))
        for path in _source_files()
        if '__name__ == "__main__"' in path.read_text()
    }
    found = with_main_guard | _console_script_files() | set(OTHER_ENTRY_POINTS)
    return sorted(found - NOT_ENTRY_POINTS)


def test_bootstrap_loads_dotenv_before_configuring_logfire(bootstrap_mocks):
    order = Mock()
    order.attach_mock(bootstrap_mocks.load_dotenv, "load_dotenv")
    order.attach_mock(bootstrap_mocks.configure, "configure")

    bootstrap.bootstrap("demo")

    assert order.mock_calls == [call.load_dotenv(), call.configure(service_name="demo")]


def test_second_call_does_nothing(bootstrap_mocks):
    bootstrap.bootstrap("first")
    bootstrap.bootstrap("second")

    bootstrap_mocks.load_dotenv.assert_called_once()
    bootstrap_mocks.configure.assert_called_once_with(service_name="first")


def _calls_bootstrap(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "bootstrap"
        for node in ast.walk(tree)
    )


def test_entry_points_are_found():
    assert len(_entry_point_files()) >= 14


@pytest.mark.parametrize("path", _entry_point_files())
def test_entry_point_calls_bootstrap(path):
    assert _calls_bootstrap(ast.parse((REPO_ROOT / path).read_text()))
