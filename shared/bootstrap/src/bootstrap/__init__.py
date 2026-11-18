"""Entry point setup, in its own package because no shared package needs dotenv or Logfire."""

import logfire
from dotenv import load_dotenv


def bootstrap(service_name: str) -> None:
    # Settings are read from the environment, some of them at import time (the
    # Postgres engine), so .env has to load before any module reads them.
    load_dotenv()
    logfire.configure(service_name=service_name)
