from functools import cache
from typing import Literal

import logfire
from pydantic import SecretStr
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


@cache
def get_telemetry_settings() -> TelemetrySettings:
    return TelemetrySettings()


def configure_telemetry(service_name: str, settings: TelemetrySettings) -> None:
    logfire.configure(
        service_name=service_name,
        send_to_logfire=SEND_TO_LOGFIRE[settings.send],
        token=settings.token.get_secret_value() if settings.token else None,
        environment=settings.environment,
    )
