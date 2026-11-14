"""The AI backends behind the normalization job.

A backend is a pure function from a prompt and a JSON schema to an answer. It never
sees a database, a file, or a tool, so the worst an injected instruction in scraped
text can do is a wrong answer, which the job's checks catch. See the police log
pipeline design, "A workflow, not an agent".
"""

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Protocol

DEFAULT_BACKEND = "claude_cli"
DEFAULT_MODEL = "haiku"
DEFAULT_TIMEOUT_SECONDS = 300

# Any of these sends `claude -p` to a billed account instead of the subscription login.
_BILLING_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
)


class AiBackendUnavailable(Exception):
    """The backend cannot be used at all this run: missing, logged out, or at its limit."""


class AiCallFailed(Exception):
    """One call failed. Its values wait for the next run; the run goes on."""


class AiBackend(Protocol):
    name: str
    model: str

    def check_ready(self) -> None:
        """Raise AiBackendUnavailable if the backend cannot be used. Makes no model call."""
        ...

    def complete(
        self,
        prompt: str,
        schema: dict[str, Any],
        timeout_s: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """One call. Raises AiCallFailed, or AiBackendUnavailable for login and limits."""
        ...


@dataclass(frozen=True)
class RecordedCall:
    prompt: str
    schema: dict[str, Any]


class FakeBackend:
    """Plays scripted replies in order, for tests. A reply that is an exception is raised."""

    name = "fake"

    def __init__(
        self, replies: list[Any] | None = None, model: str = "fake-model"
    ) -> None:
        self.replies: list[Any] = list(replies or [])
        self.model = model
        self.calls: list[RecordedCall] = []

    def check_ready(self) -> None:
        return None

    def complete(
        self,
        prompt: str,
        schema: dict[str, Any],
        timeout_s: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        self.calls.append(RecordedCall(prompt, schema))
        if not self.replies:
            raise AssertionError("no reply scripted for this call")
        reply = self.replies.pop(0)
        if isinstance(reply, TimeoutError):
            raise AiCallFailed(f"timed out: {reply}")
        if isinstance(reply, Exception):
            raise reply
        return _checked_answer(reply)


class ClaudeCliBackend:
    """One `claude -p` subprocess per batch, with every tool off.

    It runs from a new empty directory that is deleted afterwards, loads no user or
    project settings and no MCP servers, keeps no session, and takes the prompt on
    stdin. It signs in with the subscription login, so it refuses to run when
    ANTHROPIC_API_KEY or another billing variable is set.

    Confirmed against `claude --help` (2.1.325): every flag below exists. Confirmed
    by a real call: the output when the CLI is not logged in. NOT confirmed, because
    the sandbox this was written in could not reach the API: the envelope of a
    successful structured answer (read from `structured_output`, else from `result`
    as JSON text) and the wording of a usage-limit message. Both are best guesses.
    """

    name = "claude_cli"

    # Phrases in the CLI's `result` text that mean "stop this run", not "this call failed".
    _UNAVAILABLE_PHRASES = (
        "not logged in",
        "please run /login",
        "usage limit",
        "limit reached",
    )

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model

    @property
    def _binary(self) -> str:
        # Tests point CLAUDE_BIN at a fake executable.
        return os.environ.get("CLAUDE_BIN", "claude")

    def check_ready(self) -> None:
        self._refuse_an_api_key()
        if shutil.which(self._binary) is None:
            raise AiBackendUnavailable(
                f"The claude binary was not found: {self._binary!r}. "
                "Install the Claude Code CLI, or set CLAUDE_BIN."
            )

    def complete(
        self,
        prompt: str,
        schema: dict[str, Any],
        timeout_s: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        self._refuse_an_api_key()
        command = self.command(schema)
        with tempfile.TemporaryDirectory(prefix="normalize-") as empty_directory:
            try:
                finished = subprocess.run(
                    command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    cwd=empty_directory,
                    timeout=timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise AiCallFailed(f"timed out after {timeout_s} seconds") from exc
            except OSError as exc:
                raise AiBackendUnavailable(
                    f"Could not run {self._binary!r}: {exc}"
                ) from exc
        return self._answer(finished)

    def command(self, schema: dict[str, Any]) -> list[str]:
        """The exact argv of every call. The prompt is not in it: it goes in on stdin."""
        return [
            self._binary,
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema),
            "--model",
            self.model,
            "--tools",
            "",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--disable-slash-commands",
        ]

    def _refuse_an_api_key(self) -> None:
        for variable in _BILLING_VARIABLES:
            if os.environ.get(variable):
                raise AiBackendUnavailable(
                    f"{variable} is set, and claude -p would bill that account "
                    "instead of the subscription. Unset it, then run again."
                )

    def _answer(self, finished: "subprocess.CompletedProcess[str]") -> dict[str, Any]:
        envelope = _json_or_none(finished.stdout)
        if isinstance(envelope, dict) and envelope.get("is_error"):
            self._raise_for_error_result(str(envelope.get("result", "")))
        if finished.returncode != 0:
            raise AiCallFailed(
                f"claude exited with status {finished.returncode}: "
                f"{finished.stderr.strip()[:300]}"
            )
        if not isinstance(envelope, dict):
            raise AiCallFailed("claude printed no JSON result")
        answer = envelope.get("structured_output")
        if answer is None:
            answer = _json_or_none(str(envelope.get("result", "")))
        return _checked_answer(answer)

    def _raise_for_error_result(self, message: str) -> None:
        if any(phrase in message.lower() for phrase in self._UNAVAILABLE_PHRASES):
            raise AiBackendUnavailable(message)
        raise AiCallFailed(message or "claude reported an error")


def backend_from_env() -> AiBackend:
    """The backend named by NORMALIZE_AI_BACKEND, with the model from NORMALIZE_AI_MODEL."""
    name = os.environ.get("NORMALIZE_AI_BACKEND", DEFAULT_BACKEND)
    model = os.environ.get("NORMALIZE_AI_MODEL", DEFAULT_MODEL)
    if name == DEFAULT_BACKEND:
        return ClaudeCliBackend(model=model)
    raise AiBackendUnavailable(f"Unknown AI backend {name!r}.")


def _json_or_none(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


def _checked_answer(answer: Any) -> dict[str, Any]:
    if not isinstance(answer, dict):
        raise AiCallFailed("the answer is not a JSON object")
    if not answer:
        raise AiCallFailed("the answer is empty")
    return answer
