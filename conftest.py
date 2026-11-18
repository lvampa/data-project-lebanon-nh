from types import SimpleNamespace
from unittest.mock import Mock

import bootstrap
import pytest


@pytest.fixture(autouse=True)
def bootstrap_mocks(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Keep tests off .env and off Logfire, even when they call an entry point's main().

    Entry points import `bootstrap` by name, so the real function stays and the two
    things it does are replaced. The agents' sandbox cannot read .env at all.
    """
    mocks = SimpleNamespace(load_dotenv=Mock(), configure=Mock())
    monkeypatch.setattr(bootstrap, "_done", False)
    monkeypatch.setattr(bootstrap, "load_dotenv", mocks.load_dotenv)
    monkeypatch.setattr(
        bootstrap, "logfire", SimpleNamespace(configure=mocks.configure)
    )
    return mocks
