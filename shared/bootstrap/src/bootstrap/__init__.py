"""Entry point setup, in its own package so the other shared packages stay free of Logfire."""

import logfire
from dotenv import load_dotenv

_done = False


def bootstrap(service_name: str) -> None:
    """Load .env, then configure Logfire. The first call wins and later calls do nothing.

    Some entry points start a framework that bootstraps again, and the entry point
    should keep its own service name.
    """
    global _done
    if _done:
        return
    _done = True
    load_dotenv()
    logfire.configure(service_name=service_name)
