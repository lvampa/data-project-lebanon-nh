from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import Mock

import bootstrap
import pytest
from mongo import get_db


def _silence_bootstrap(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Replace the two things bootstrap does, so tests never read .env or reach Logfire.

    Entry points import `bootstrap` by name, so the real function stays and its two
    calls are replaced. The agents' sandbox cannot read .env at all.
    """
    mocks = SimpleNamespace(load_dotenv=Mock(), configure=Mock())
    monkeypatch.setattr(bootstrap, "_done", False)
    monkeypatch.setattr(bootstrap, "load_dotenv", mocks.load_dotenv)
    monkeypatch.setattr(
        bootstrap, "logfire", SimpleNamespace(configure=mocks.configure)
    )
    return mocks


_session_patch = pytest.MonkeyPatch()


def pytest_configure(config: pytest.Config) -> None:
    # Modules such as api.main bootstrap when a test file imports them, which is
    # during collection and before any fixture runs.
    _silence_bootstrap(_session_patch)
    # Subprocesses, such as the one test_migrate starts, configure Logfire for real.
    _session_patch.setenv("LOGFIRE_SEND_TO_LOGFIRE", "false")


def pytest_unconfigure(config: pytest.Config) -> None:
    _session_patch.undo()


@pytest.fixture(autouse=True)
def bootstrap_mocks(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Fresh mocks and an unused flag for each test."""
    return _silence_bootstrap(monkeypatch)


@pytest.fixture(autouse=True)
def _fresh_mongo_client() -> Iterator[None]:
    """A test that changes MONGO_* gets a client built from them, not a cached one."""
    get_db.cache_clear()
    yield
    get_db.cache_clear()
