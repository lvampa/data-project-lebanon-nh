"""Entry point setup: load .env, then configure Logfire.

Library code never imports this. Entry points call it first, and so does Alembic's
env.py when it runs from the CLI.
"""

from dotenv import load_dotenv

from .telemetry import configure_telemetry, get_telemetry_settings

_done = False


def bootstrap(service_name: str) -> None:
    """The first successful call wins and later calls do nothing.

    Some entry points start a framework that bootstraps again, and the entry point
    should keep its own service name. A call that raises can be retried.
    """
    global _done
    if _done:
        return
    load_dotenv()
    configure_telemetry(service_name, get_telemetry_settings())
    _done = True
