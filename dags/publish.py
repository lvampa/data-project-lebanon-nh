"""Run a command with an Airflow Connection's R2 settings in its environment only.

The key pair, endpoint and bucket go to the child process and nowhere else: not this
process's environment, not the log, not another task.
"""

import logging
import os
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

log = logging.getLogger("airflow.task")


class R2Connection(Protocol):
    login: str | None
    password: str | None

    @property
    def extra_dejson(self) -> Mapping[str, Any]: ...


def r2_env(connection: R2Connection) -> dict[str, str]:
    """The variables scripts/deploy-data.sh reads, from the `r2_data` Connection."""
    extra = connection.extra_dejson
    values = {
        "AWS_ACCESS_KEY_ID": connection.login,
        "AWS_SECRET_ACCESS_KEY": connection.password,
        "R2_ENDPOINT": extra.get("endpoint_url"),
        "R2_BUCKET": extra.get("bucket"),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        # The names only. A value is never in the message.
        raise ValueError(
            f"the r2_data Connection has no value for {', '.join(missing)}"
        )
    return {name: str(value) for name, value in values.items()}


def run_with_r2(command: Sequence[str], cwd: str, connection: R2Connection) -> None:
    """Run `command`, log its output, and raise if it fails."""
    env = {**os.environ, **r2_env(connection)}
    with subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            log.info(line.rstrip())
    if process.returncode:
        raise subprocess.CalledProcessError(process.returncode, command[:3])
