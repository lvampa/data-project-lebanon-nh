"""Entry point setup: load .env, then configure Logfire.

Library code never imports this. Entry points call it first, and so does Alembic's
env.py when it runs from the CLI.
"""

import logfire
from dotenv import load_dotenv

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
    # Without a token, nothing is sent: a local run, a hand run or a test works
    # without Logfire credentials.
    logfire.configure(service_name=service_name, send_to_logfire="if-token-present")
    _done = True
