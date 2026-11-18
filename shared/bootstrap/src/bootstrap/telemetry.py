import logging
import sys
from functools import cache
from pathlib import Path
from typing import Literal, TextIO, cast

import logfire
from logfire import ConsoleOptions, LogfireLoggingHandler
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SEND_TO_LOGFIRE: dict[str, bool | Literal["if-token-present"]] = {
    "always": True,
    "never": False,
    "if-token-present": "if-token-present",
}


class TelemetrySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOGFIRE_")

    # "if-token-present" means a local run, a hand run or a test works without
    # Logfire credentials and sends nothing.
    send: Literal["always", "never", "if-token-present"] = "if-token-present"
    token: SecretStr | None = None
    environment: str | None = None
    # Off when unset. For debugging a hand run, for example LOG_FILE=tmp/logs/dev.log.
    log_file: Path | None = Field(None, validation_alias="LOG_FILE")


@cache
def get_telemetry_settings() -> TelemetrySettings:
    return TelemetrySettings()


class _Tee:
    """Logfire's console output, copied into the log file."""

    def __init__(self, *streams: TextIO) -> None:
        self._streams = streams

    def write(self, text: str) -> int:
        for stream in self._streams:
            stream.write(text)
        return len(text)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def configure_telemetry(service_name: str, settings: TelemetrySettings) -> None:
    console = None
    if settings.log_file:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file = settings.log_file.open("a", buffering=1)
        tee = cast(
            TextIO, _Tee(sys.stdout, log_file)
        )  # Logfire only calls write and flush.
        console = ConsoleOptions(output=tee, colors="never")
    logfire.configure(
        service_name=service_name,
        send_to_logfire=SEND_TO_LOGFIRE[settings.send],
        token=settings.token.get_secret_value() if settings.token else None,
        environment=settings.environment,
        console=console,
    )


def attach_log_handlers(settings: TelemetrySettings) -> None:
    """Send stdlib warnings to Logfire, and everything to the log file if one is set.

    Scrapy installs its own root handler for the terminal and keeps any others, so
    these sit beside it. Logfire already prints what it forwards, so its handler
    turns console output off to avoid a second terminal line.
    """
    root = logging.getLogger()
    root.addHandler(LogfireLoggingHandler(level=logging.WARNING, console_log=False))
    if settings.log_file:
        file_handler = logging.FileHandler(settings.log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(file_handler)
