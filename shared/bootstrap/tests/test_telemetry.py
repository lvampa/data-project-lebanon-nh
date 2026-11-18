import logging

import pytest
from bootstrap.telemetry import (
    TelemetrySettings,
    attach_log_handlers,
    configure_telemetry,
)


@pytest.mark.parametrize(
    ("send", "expected"),
    [("always", True), ("never", False), ("if-token-present", "if-token-present")],
)
def test_send_maps_onto_logfires_send_to_logfire(bootstrap_mocks, send, expected):
    configure_telemetry("demo", TelemetrySettings(send=send))

    kwargs = bootstrap_mocks.configure.call_args.kwargs
    assert kwargs["send_to_logfire"] == expected


def test_send_is_read_from_logfire_send(monkeypatch):
    monkeypatch.setenv("LOGFIRE_SEND", "always")

    assert TelemetrySettings().send == "always"


@pytest.fixture
def root_handlers():
    root = logging.getLogger()
    before = list(root.handlers)
    yield root.handlers
    for handler in set(root.handlers) - set(before):
        root.removeHandler(handler)
        handler.close()


def _handlers_writing_to(handlers, path):
    return [
        h
        for h in handlers
        if isinstance(h, logging.FileHandler) and h.baseFilename == str(path)
    ]


def test_log_file_adds_a_file_handler_only_when_set(root_handlers, tmp_path):
    log_file = tmp_path / "dev.log"

    attach_log_handlers(TelemetrySettings())
    assert _handlers_writing_to(root_handlers, log_file) == []

    attach_log_handlers(TelemetrySettings(LOG_FILE=log_file))
    assert len(_handlers_writing_to(root_handlers, log_file)) == 1
