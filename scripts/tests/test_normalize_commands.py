"""The two commands are installed as console scripts, so `uv run normalize` works."""

from importlib.metadata import entry_points

import pytest

from scripts.normalize import geocode, job


@pytest.mark.parametrize(
    ("command", "main"),
    [("normalize", job.main), ("geocode", geocode.main)],
)
def test_the_command_is_a_console_script_that_runs_main(command, main):
    [script] = [
        entry
        for entry in entry_points(group="console_scripts")
        if entry.name == command
        and entry.dist is not None
        and entry.dist.name == "scripts"
    ]

    assert script.load() is main
