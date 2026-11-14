"""The normalization command: its exit codes, its lock, and what it prints."""

from datetime import date, datetime

import pytest
from postgres.lock import police_log_lock
from postgres.models.log_entry import LogEntry

from scripts.normalize import job
from scripts.normalize.backends import AiBackendUnavailable, AiCallFailed, FakeBackend

NOW = datetime(2026, 11, 13)


def add_type(session, raw: str) -> None:
    session.add(
        LogEntry(
            case_number=f"c-{raw}",
            source_url="https://example.com/log.pdf",
            log_date=date(2026, 5, 11),
            incident_type=raw,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.commit()


def answer(raw: str) -> dict[str, object]:
    return {
        "items": [
            {
                "raw": raw,
                "category": "Police",
                "normalized_type": "Noise complaint",
                "unsure": False,
            }
        ]
    }


def test_a_run_that_stores_values_exits_zero_and_says_what_it_did(
    db_session, ai_calls, capsys
):
    add_type(db_session, "NOISE")
    backend = FakeBackend(replies=[answer("NOISE")])

    status = job.main(["--field", "incident_type"], backend_factory=lambda: backend)

    out = capsys.readouterr().out
    assert status == 0
    assert "incident_type: 1 stored, 0 discarded, 0 still waiting." in out
    assert "1 AI calls, 0 failed." in out


def test_a_run_with_nothing_waiting_makes_no_call_and_exits_zero(db_session, ai_calls):
    backend = FakeBackend(replies=[])

    assert job.main([], backend_factory=lambda: backend) == 0
    assert backend.calls == []


def test_a_run_where_every_ai_call_fails_exits_non_zero(db_session, ai_calls, capsys):
    add_type(db_session, "NOISE")
    backend = FakeBackend(replies=[AiCallFailed("timed out")])

    status = job.main(["--field", "incident_type"], backend_factory=lambda: backend)

    assert status == 1
    assert "1 AI calls, 1 failed." in capsys.readouterr().out


def test_one_failed_call_among_good_ones_still_exits_zero(db_session, ai_calls):
    add_type(db_session, "A")
    add_type(db_session, "B")
    # Two values in one batch: the one call works, so not every call failed.
    backend = FakeBackend(
        replies=[
            {
                "items": [
                    {
                        "raw": raw,
                        "category": "Police",
                        "normalized_type": "Noise",
                        "unsure": False,
                    }
                    for raw in ("A", "B")
                ]
            }
        ]
    )

    assert job.main(["--field", "incident_type"], backend_factory=lambda: backend) == 0


def test_a_logged_out_backend_stops_the_run_and_exits_non_zero(
    db_session, ai_calls, capsys
):
    add_type(db_session, "NOISE")
    backend = FakeBackend(replies=[AiBackendUnavailable("Not logged in")])

    status = job.main(["--field", "incident_type"], backend_factory=lambda: backend)

    assert status == 1
    assert "logged out or at its limit" in capsys.readouterr().out


def test_another_police_log_job_running_stops_the_run_before_any_call(
    db_session, ai_calls, test_engine, capsys
):
    add_type(db_session, "NOISE")
    backend = FakeBackend(replies=[answer("NOISE")])

    with police_log_lock(test_engine) as acquired:
        assert acquired
        status = job.main(["--field", "incident_type"], backend_factory=lambda: backend)

    assert status == 1
    assert backend.calls == []
    assert "Another police log job is running" in capsys.readouterr().err


def test_the_lock_is_released_when_the_run_ends(db_session, ai_calls, test_engine):
    job.main([], backend_factory=lambda: FakeBackend(replies=[]))

    with police_log_lock(test_engine) as acquired:
        assert acquired


def test_a_backend_that_cannot_run_exits_non_zero_before_touching_anything(
    db_session, ai_calls, capsys
):
    class NotReady(FakeBackend):
        def check_ready(self) -> None:
            raise AiBackendUnavailable("The claude binary was not found")

    add_type(db_session, "NOISE")
    backend = NotReady(replies=[answer("NOISE")])

    status = job.main([], backend_factory=lambda: backend)

    assert status == 1
    assert backend.calls == []
    assert "Cannot run: The claude binary was not found" in capsys.readouterr().err


def test_an_api_key_in_the_environment_stops_the_default_backend(
    db_session, ai_calls, monkeypatch, capsys
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("NORMALIZE_AI_BACKEND", raising=False)

    status = job.main([])

    assert status == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_field_picks_one_field_and_an_unknown_field_is_refused():
    with pytest.raises(SystemExit):
        job.main(["--field", "officer"])
