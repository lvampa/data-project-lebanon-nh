"""A record of every AI call the normalization job makes, with its prompt and answer.

Like the raw archive it is a side copy: a write that fails is logged and returns
None, so the job stores its results without the reference.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

import logfire
from pymongo.errors import PyMongoError

from .archive import RawCollection, is_unreachable, quick_collection
from .client import MongoDB

COLLECTION = "ai_calls"

Outcome = Literal["ok", "partial", "failed", "unavailable"]


@dataclass(frozen=True)
class AiCall:
    field: str
    raw_values: list[str]
    prompt: str
    # As the backend returned it; None when the call never got an answer.
    raw_answer: str | None
    accepted: list[dict[str, Any]]
    ai_backend: str
    model: str
    prompt_version: str
    duration_ms: int
    outcome: Outcome
    error: str | None
    called_at: datetime


def ai_calls_collection(settings: MongoDB) -> RawCollection:
    return quick_collection(settings, COLLECTION)


class AiCallLog:
    def __init__(self, collection: RawCollection) -> None:
        self._collection = collection
        self.is_down = False

    def record(self, call: AiCall) -> str | None:
        """Store one call, and return its ID, or None when the write failed.

        The ID comes from MongoDB, never the client, so Postgres never points at a
        record that was not written.
        """
        if self.is_down:
            return None
        try:
            result = self._collection.insert_one(asdict(call))
        except PyMongoError as exc:
            if is_unreachable(exc):
                self.is_down = True
                logfire.error(
                    "ai call log unreachable; dropping its writes for this run",
                    error=repr(exc),
                )
            else:
                logfire.warning("ai call record failed", error=repr(exc))
            return None
        return str(result.inserted_id)

    def calls(self, field: str, prompt_version: str) -> list[dict[str, Any]]:
        """The calls for one field and prompt version, newest first."""
        return list(
            self._collection.find(
                {"field": field, "prompt_version": prompt_version}
            ).sort("called_at", -1)
        )
