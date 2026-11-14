import socket
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from mongo.ai_calls import AiCall, AiCallLog, ai_calls_collection
from mongo.client import MongoDB


def call(**overrides: Any) -> AiCall:
    values: dict[str, Any] = {
        "field": "incident_type",
        "raw_values": ["MV Complaint"],
        "prompt": "Normalize these incident types.",
        "raw_answer": '[{"raw": "MV Complaint", "category": "Traffic"}]',
        "accepted": [{"raw": "MV Complaint", "category": "Traffic"}],
        "ai_backend": "claude_cli",
        "model": "claude-sonnet-5-5",
        "prompt_version": "incident_type-1",
        "duration_ms": 8400,
        "outcome": "ok",
        "error": None,
        "called_at": datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
    }
    return AiCall(**{**values, **overrides})


def test_a_call_is_stored_and_its_id_returned(ai_calls):
    call_id = AiCallLog(ai_calls).record(call())

    assert call_id is not None
    stored = ai_calls.find_one({"_id": ObjectId(call_id)})
    assert stored["raw_answer"].startswith('[{"raw"')
    assert stored["accepted"] == [{"raw": "MV Complaint", "category": "Traffic"}]
    assert (stored["ai_backend"], stored["outcome"]) == ("claude_cli", "ok")


def test_a_failed_call_is_stored_too(ai_calls):
    failed = call(raw_answer=None, accepted=[], outcome="failed", error="timed out")

    call_id = AiCallLog(ai_calls).record(failed)

    stored = ai_calls.find_one({"_id": ObjectId(call_id)})
    assert (stored["outcome"], stored["error"]) == ("failed", "timed out")


def test_calls_are_listed_by_field_and_prompt_version_newest_first(ai_calls):
    log = AiCallLog(ai_calls)
    for day in (5, 7, 6):
        log.record(call(called_at=datetime(2026, 11, day, tzinfo=UTC)))
    log.record(call(prompt_version="incident_type-2"))
    log.record(call(field="disposition"))

    listed = log.calls("incident_type", "incident_type-1")

    assert [c["called_at"].day for c in listed] == [7, 6, 5]


def closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_an_unreachable_server_returns_none_without_raising(monkeypatch):
    monkeypatch.setenv("MONGO_HOST", "127.0.0.1")
    monkeypatch.setenv("MONGO_PORT", str(closed_port()))
    log = AiCallLog(ai_calls_collection(MongoDB()))

    assert log.record(call()) is None
    assert log.is_down is True
    # Once down, later calls do not wait on the server again.
    assert log.record(call()) is None
