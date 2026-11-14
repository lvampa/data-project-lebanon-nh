import json
import stat
import sys
from pathlib import Path

import pytest

from scripts.normalize.backends import (
    AiBackendUnavailable,
    AiCallFailed,
    ClaudeCliBackend,
    FakeBackend,
    backend_from_env,
)

SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array"}},
    "required": ["items"],
}
ANSWER = {"items": [{"raw": "MV COMPLAINT", "normalized": "Motor vehicle complaint"}]}

# What the real CLI printed when it was not logged in, captured on 2026-11-13 with
# `claude -p --output-format json` and an empty config directory. The other outputs
# below are NOT captured from the real CLI: the sandbox this was built in could not
# reach the API. Confirm them with one real call before relying on them.
REAL_LOGIN_FAILURE = {
    "type": "result",
    "subtype": "success",
    "is_error": True,
    "terminal_reason": "api_error",
    "api_error_status": None,
    "result": "Not logged in · Please run /login",
}

FAKE_CLAUDE = '''\
#!{python}
"""Stands in for the claude binary: records how it was called, then plays a mode."""
import json
import os
import sys
import time
from pathlib import Path

log = Path(os.environ["FAKE_CLAUDE_LOG"])
log.mkdir(exist_ok=True)
(log / "argv.json").write_text(json.dumps(sys.argv[1:]))
(log / "cwd.txt").write_text(os.getcwd())
(log / "cwd_listing.json").write_text(json.dumps(sorted(os.listdir("."))))
(log / "stdin.txt").write_text(sys.stdin.read())

mode = os.environ["FAKE_CLAUDE_MODE"]
reply = json.loads(os.environ.get("FAKE_CLAUDE_REPLY", "null"))
if mode == "sleep":
    time.sleep(30)
elif mode == "garbage":
    print("this is not json")
elif mode == "crash":
    print("boom", file=sys.stderr)
    sys.exit(2)
else:
    print(json.dumps(reply))
    sys.exit(1 if reply and reply.get("is_error") else 0)
'''


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    """A fake `claude` executable. Set `.mode` and `.reply`; read `.log` afterwards."""
    log = tmp_path / "log"
    exe = tmp_path / "fake-claude"
    exe.write_text(FAKE_CLAUDE.format(python=sys.executable))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("CLAUDE_BIN", str(exe))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class Fake:
        def __init__(self) -> None:
            self.log = log

        def play(self, mode: str, reply: object = None) -> None:
            monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
            monkeypatch.setenv("FAKE_CLAUDE_REPLY", json.dumps(reply))

        def recorded(self, name: str) -> object:
            return json.loads((log / name).read_text())

    return Fake()


def cli_result(answer: object) -> dict[str, object]:
    """The CLI's JSON envelope around an answer. Shape unconfirmed; see above."""
    return {"type": "result", "is_error": False, "structured_output": answer}


# --- one contract suite for every backend ---


@pytest.fixture(params=["fake", "claude_cli"])
def contract(request, fake_claude):
    """A backend and a way to make it fail, so one suite covers all of them."""
    if request.param == "fake":
        fake = FakeBackend()

        def arrange_fake(case: str) -> None:
            replies = {
                "valid": ANSWER,
                "empty": {},
                "malformed": "not an object",
                "timeout": TimeoutError("took too long"),
                "login": AiBackendUnavailable("Not logged in"),
            }
            fake.replies = [replies[case]]

        return fake, arrange_fake

    cli = ClaudeCliBackend(model="haiku")

    def arrange(case: str) -> None:
        match case:
            case "valid":
                fake_claude.play("ok", cli_result(ANSWER))
            case "empty":
                fake_claude.play("ok", cli_result({}))
            case "malformed":
                fake_claude.play("garbage")
            case "timeout":
                fake_claude.play("sleep")
            case "login":
                fake_claude.play("ok", REAL_LOGIN_FAILURE)

    return cli, arrange


def test_contract_a_valid_answer_is_returned(contract):
    backend, arrange = contract
    arrange("valid")

    assert backend.complete("prompt", SCHEMA, timeout_s=5) == ANSWER


def test_contract_an_empty_answer_fails_the_call(contract):
    backend, arrange = contract
    arrange("empty")

    with pytest.raises(AiCallFailed, match="empty"):
        backend.complete("prompt", SCHEMA, timeout_s=5)


def test_contract_a_malformed_answer_fails_the_call(contract):
    backend, arrange = contract
    arrange("malformed")

    with pytest.raises(AiCallFailed):
        backend.complete("prompt", SCHEMA, timeout_s=5)


def test_contract_a_timeout_fails_the_call_and_does_not_stop_the_run(contract):
    backend, arrange = contract
    arrange("timeout")

    with pytest.raises(AiCallFailed) as raised:
        backend.complete("prompt", SCHEMA, timeout_s=1)

    assert not isinstance(raised.value, AiBackendUnavailable)


def test_contract_a_login_failure_stops_the_run(contract):
    backend, arrange = contract
    arrange("login")

    with pytest.raises(AiBackendUnavailable):
        backend.complete("prompt", SCHEMA, timeout_s=5)


# --- FakeBackend ---


def test_the_fake_returns_its_replies_in_order_and_records_each_call():
    backend = FakeBackend(replies=[{"items": [1]}, {"items": [2]}])

    first = backend.complete("one", SCHEMA)
    second = backend.complete("two", SCHEMA)

    assert (first, second) == ({"items": [1]}, {"items": [2]})
    assert [call.prompt for call in backend.calls] == ["one", "two"]
    assert backend.calls[0].schema == SCHEMA


def test_the_fake_fails_loudly_when_a_test_made_an_unscripted_call():
    backend = FakeBackend(replies=[])

    with pytest.raises(AssertionError, match="no reply scripted"):
        backend.complete("prompt", SCHEMA)


def test_the_fake_raises_a_scripted_exception():
    backend = FakeBackend(replies=[AiCallFailed("boom")])

    with pytest.raises(AiCallFailed, match="boom"):
        backend.complete("prompt", SCHEMA)


# --- ClaudeCliBackend ---


def test_every_call_runs_with_tools_off_and_no_settings_hooks_or_mcp(fake_claude):
    fake_claude.play("ok", cli_result(ANSWER))

    ClaudeCliBackend(model="haiku").complete("prompt", SCHEMA)

    argv = fake_claude.recorded("argv.json")
    assert argv == [
        "-p",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(SCHEMA),
        "--model",
        "haiku",
        "--tools",
        "",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--disable-slash-commands",
    ]


def test_the_prompt_goes_in_on_stdin_not_on_the_command_line(fake_claude):
    fake_claude.play("ok", cli_result(ANSWER))

    ClaudeCliBackend(model="haiku").complete("the raw values", SCHEMA)

    assert fake_claude.recorded("argv.json").count("the raw values") == 0
    assert (fake_claude.log / "stdin.txt").read_text() == "the raw values"


def test_each_call_starts_in_a_new_empty_directory_that_is_removed_afterwards(
    fake_claude, tmp_path
):
    fake_claude.play("ok", cli_result(ANSWER))
    backend = ClaudeCliBackend(model="haiku")

    backend.complete("one", SCHEMA)
    first_cwd = Path((fake_claude.log / "cwd.txt").read_text())
    backend.complete("two", SCHEMA)
    second_cwd = Path((fake_claude.log / "cwd.txt").read_text())

    assert fake_claude.recorded("cwd_listing.json") == []
    assert first_cwd != second_cwd
    assert not first_cwd.exists()
    assert not second_cwd.exists()


def test_the_working_directory_is_removed_even_when_the_call_times_out(fake_claude):
    fake_claude.play("sleep")

    with pytest.raises(AiCallFailed):
        ClaudeCliBackend(model="haiku").complete("prompt", SCHEMA, timeout_s=1)

    assert not Path((fake_claude.log / "cwd.txt").read_text()).exists()


def test_the_answer_may_come_as_json_text_in_the_result_field(fake_claude):
    fake_claude.play(
        "ok", {"type": "result", "is_error": False, "result": json.dumps(ANSWER)}
    )

    assert ClaudeCliBackend(model="haiku").complete("prompt", SCHEMA) == ANSWER


def test_a_nonzero_exit_without_a_login_message_is_an_ordinary_failure(fake_claude):
    fake_claude.play("crash")

    with pytest.raises(AiCallFailed, match="status 2") as raised:
        ClaudeCliBackend(model="haiku").complete("prompt", SCHEMA)

    assert not isinstance(raised.value, AiBackendUnavailable)


@pytest.mark.parametrize(
    "message",
    [
        "Not logged in · Please run /login",
        "Claude usage limit reached. Your limit will reset at 5pm.",
    ],
    ids=["login", "usage_limit_best_guess"],
)
def test_login_and_usage_limit_messages_stop_the_run(fake_claude, message):
    fake_claude.play("ok", {"type": "result", "is_error": True, "result": message})

    with pytest.raises(AiBackendUnavailable, match="logged in|limit"):
        ClaudeCliBackend(model="haiku").complete("prompt", SCHEMA)


def test_any_other_error_result_is_an_ordinary_failure(fake_claude):
    fake_claude.play(
        "ok", {"type": "result", "is_error": True, "result": "Overloaded, try again"}
    )

    with pytest.raises(AiCallFailed, match="Overloaded") as raised:
        ClaudeCliBackend(model="haiku").complete("prompt", SCHEMA)

    assert not isinstance(raised.value, AiBackendUnavailable)


def test_check_ready_passes_when_the_binary_exists_and_makes_no_call(fake_claude):
    ClaudeCliBackend(model="haiku").check_ready()

    assert not fake_claude.log.exists()


def test_check_ready_fails_when_the_binary_is_missing(monkeypatch):
    monkeypatch.setenv("CLAUDE_BIN", "/no/such/claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(AiBackendUnavailable, match="not found"):
        ClaudeCliBackend(model="haiku").check_ready()


def test_an_api_key_in_the_environment_stops_the_run_before_any_call(
    fake_claude, monkeypatch
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    backend = ClaudeCliBackend(model="haiku")

    with pytest.raises(AiBackendUnavailable, match="ANTHROPIC_API_KEY"):
        backend.check_ready()
    with pytest.raises(AiBackendUnavailable, match="ANTHROPIC_API_KEY"):
        backend.complete("prompt", SCHEMA)

    assert not fake_claude.log.exists()


# --- configuration ---


def test_the_default_backend_is_claude_cli_with_haiku(monkeypatch):
    monkeypatch.delenv("NORMALIZE_AI_BACKEND", raising=False)
    monkeypatch.delenv("NORMALIZE_AI_MODEL", raising=False)

    backend = backend_from_env()

    assert isinstance(backend, ClaudeCliBackend)
    assert (backend.name, backend.model) == ("claude_cli", "haiku")


def test_the_model_comes_from_configuration(monkeypatch):
    monkeypatch.setenv("NORMALIZE_AI_MODEL", "sonnet")

    assert backend_from_env().model == "sonnet"


def test_an_unknown_backend_is_an_error_that_names_it(monkeypatch):
    monkeypatch.setenv("NORMALIZE_AI_BACKEND", "carrier-pigeon")

    with pytest.raises(AiBackendUnavailable, match="carrier-pigeon"):
        backend_from_env()
