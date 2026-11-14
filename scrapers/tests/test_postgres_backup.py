from datetime import UTC, datetime
from pathlib import Path

import pytest
from maintenance import postgres_backup
from maintenance.postgres_backup import BackupError, back_up, pgpass_line
from sqlalchemy import URL

NOW = datetime(2026, 11, 13, 22, 10, tzinfo=UTC)
PASSWORD = "p:ss\\w0rd"
URL_WITH_PASSWORD = URL.create(
    "postgresql+psycopg2",
    username="app",
    password=PASSWORD,
    host="localhost",
    port=5432,
    database="app",
)


class FakeDump:
    """Stands in for pg_dump: records the command and writes the dump file."""

    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.commands: list[list[str]] = []
        self.environments: list[dict[str, str]] = []
        self.passfile = ""

    def __call__(self, command, env) -> int:
        self.commands.append(list(command))
        self.environments.append(dict(env))
        self.passfile = Path(env["PGPASSFILE"]).read_text()
        file_option = next(a for a in command if a.startswith("--file="))
        Path(file_option.removeprefix("--file=")).write_bytes(b"PGDMP partial")
        return self.returncode


def test_the_password_line_escapes_colons_and_backslashes():
    assert pgpass_line(URL_WITH_PASSWORD) == r"localhost:5432:*:app:p\:ss\\w0rd" + "\n"


def test_each_run_writes_a_new_dated_file_and_keeps_the_old_ones(tmp_path):
    older = tmp_path / "app-20261101T020000Z.dump"
    older.write_bytes(b"older")
    tool = FakeDump()

    dest = back_up(tmp_path, URL_WITH_PASSWORD, NOW, tool)

    assert dest.name == "app-20261113T221000Z.dump"
    assert dest.read_bytes() == b"PGDMP partial"
    assert older.read_bytes() == b"older"


def test_the_password_stays_out_of_the_command_the_environment_and_the_file_name(
    tmp_path,
):
    tool = FakeDump()

    dest = back_up(tmp_path, URL_WITH_PASSWORD, NOW, tool)

    assert tool.passfile == pgpass_line(URL_WITH_PASSWORD)
    [command] = tool.commands
    assert command[:2] == ["pg_dump", "-Fc"]
    assert not any(PASSWORD in arg for arg in command)
    assert PASSWORD not in "".join(tool.environments[0].values())
    assert PASSWORD not in dest.name


def test_a_failed_dump_raises_and_deletes_its_partial_file_only(tmp_path):
    older = tmp_path / "app-20261101T020000Z.dump"
    older.write_bytes(b"older")

    with pytest.raises(BackupError, match="status 2"):
        back_up(tmp_path, URL_WITH_PASSWORD, NOW, FakeDump(returncode=2))

    assert [p.name for p in tmp_path.iterdir()] == [older.name]


def test_an_interrupted_dump_leaves_no_file_and_keeps_the_old_ones(tmp_path):
    older = tmp_path / "app-20261101T020000Z.dump"
    older.write_bytes(b"older")

    def interrupted(command, env) -> int:
        FakeDump()(command, env)
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        back_up(tmp_path, URL_WITH_PASSWORD, NOW, interrupted)

    assert [p.name for p in tmp_path.iterdir()] == [older.name]


def test_a_second_run_in_the_same_second_does_not_overwrite_the_first(tmp_path):
    first = back_up(tmp_path, URL_WITH_PASSWORD, NOW, FakeDump())

    with pytest.raises(BackupError, match="already exists"):
        back_up(tmp_path, URL_WITH_PASSWORD, NOW, FakeDump(returncode=1))

    assert first.read_bytes() == b"PGDMP partial"


def test_the_script_exits_non_zero_when_the_folder_is_missing(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(postgres_backup, "BACKUP_DIR", tmp_path / "missing")
    monkeypatch.setattr(postgres_backup.logfire, "configure", lambda: None)

    assert postgres_backup.main() == 1
    assert str(tmp_path / "missing") in capsys.readouterr().err
