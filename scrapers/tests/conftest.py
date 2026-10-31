from unittest.mock import MagicMock

import pytest


class FakeSession:
    """Tracks which statements a SQLAlchemy session would have committed."""

    def __init__(self) -> None:
        self.pending: list = []
        self.committed: list = []
        self.transactions: list[list] = []
        self.fail_on_call: int | None = None
        self.returned_rows: list = []
        self._calls = 0

    def execute(self, statement):
        self._calls += 1
        if self._calls == self.fail_on_call:
            raise RuntimeError("database error")
        self.pending.append(statement)
        result = MagicMock()
        result.scalar_one.return_value = 1
        result.all.return_value = self.returned_rows
        return result

    def commit(self) -> None:
        self.committed.extend(self.pending)
        self.transactions.append(list(self.pending))
        self.pending.clear()

    def rollback(self) -> None:
        self.pending.clear()

    def close(self) -> None:
        pass

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


@pytest.fixture
def fake_session():
    return FakeSession()
