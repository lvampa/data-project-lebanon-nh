from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def fail_on_execute(monkeypatch) -> Callable[[Session, int], None]:
    """Make the nth `execute` on a real session raise, as a database error would."""

    def arrange(session: Session, call_number: int) -> None:
        real_execute = session.execute
        calls = 0

        def execute(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == call_number:
                raise RuntimeError("database error")
            return real_execute(*args, **kwargs)

        monkeypatch.setattr(session, "execute", execute)

    return arrange
