from unittest.mock import MagicMock

import pytest


class FakeSession:
    """Tracks which statements a SQLAlchemy session would have committed."""

    def __init__(self) -> None:
        self.pending: list = []
        self.committed: list = []
        self.fail_on_call: int | None = None
        self._calls = 0

    def execute(self, statement):
        self._calls += 1
        if self._calls == self.fail_on_call:
            raise RuntimeError("database error")
        self.pending.append(statement)
        result = MagicMock()
        result.scalar_one.return_value = 1
        return result

    def commit(self) -> None:
        self.committed.extend(self.pending)
        self.pending.clear()

    def rollback(self) -> None:
        self.pending.clear()

    def close(self) -> None:
        pass


@pytest.fixture
def fake_session():
    return FakeSession()
