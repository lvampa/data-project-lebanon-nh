"""Pytest plugin that keeps tests off .env and off Logfire.

It loads through the `pytest11` entry point, so every suite in the workspace gets it,
from whichever directory pytest runs.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import bootstrap
import pytest
from bootstrap import telemetry

_session_patch = pytest.MonkeyPatch()


def _silence_bootstrap(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Replace the two things bootstrap does.

    Entry points import `bootstrap` by name, so the real function stays and its two
    calls are replaced. The agents' sandbox cannot read .env at all.
    """
    mocks = SimpleNamespace(load_dotenv=Mock(), configure=Mock())
    monkeypatch.setattr(bootstrap, "_done", False)
    monkeypatch.setattr(bootstrap, "load_dotenv", mocks.load_dotenv)
    monkeypatch.setattr(
        telemetry, "logfire", SimpleNamespace(configure=mocks.configure)
    )
    telemetry.get_telemetry_settings.cache_clear()
    return mocks


def pytest_configure(config: pytest.Config) -> None:
    # Modules may bootstrap while a test file imports them, which is during collection
    # and before any fixture runs.
    _silence_bootstrap(_session_patch)
    # Subprocesses, such as the one test_migrate starts, configure Logfire for real.
    _session_patch.setenv("LOGFIRE_SEND", "never")


def pytest_unconfigure(config: pytest.Config) -> None:
    _session_patch.undo()


@pytest.fixture(autouse=True)
def bootstrap_mocks(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Fresh mocks and an unused flag for each test."""
    return _silence_bootstrap(monkeypatch)
