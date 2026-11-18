import pytest
from bootstrap.telemetry import TelemetrySettings, configure_telemetry


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
