from datetime import UTC, datetime
from pathlib import Path

import pytest
from maintenance import mongo_backup
from maintenance.mongo_backup import BackupError, back_up, check_writable, prune
from mongo.client import MongoDB

NOW = datetime(2026, 11, 7, 2, 0, tzinfo=UTC)


class FakeTool:
    """Stands in for mongodump: records the command and writes the archive."""

    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.commands: list[list[str]] = []
        self.config = ""

    def __call__(self, command) -> int:
        self.commands.append(list(command))
        options = dict(arg.split("=", 1) for arg in command[1:] if "=" in arg)
        self.config = Path(options["--config"]).read_text()
        Path(options["--archive"]).write_bytes(b"partial dump")
        return self.returncode


def settings(monkeypatch) -> MongoDB:
    monkeypatch.setenv("MONGO_PASSWORD", "s3cret")
    monkeypatch.setenv("MONGO_DB", "scraped_data")
    return MongoDB()


def test_a_missing_folder_fails_with_its_name(tmp_path):
    missing = tmp_path / "mongo"

    with pytest.raises(BackupError, match=str(missing)):
        check_writable(missing)


def test_a_read_only_folder_fails_with_its_name(tmp_path):
    folder = tmp_path / "mongo"
    folder.mkdir()
    folder.chmod(0o500)
    try:
        with pytest.raises(BackupError, match=f"{folder} is not writable"):
            check_writable(folder)
    finally:
        folder.chmod(0o700)


def test_a_backup_is_written_without_the_password_on_the_command_line(
    tmp_path, monkeypatch
):
    tool = FakeTool()

    dest = back_up(tmp_path, settings(monkeypatch), NOW, tool)

    [command] = tool.commands
    assert command[0] == "mongodump"
    assert {"--db=scraped_data", "--gzip", f"--archive={dest}"} <= set(command)
    assert not any("s3cret" in arg for arg in command)
    assert tool.config == 'password: "s3cret"\n'
    assert dest.name == "scraped_data-20261107T020000Z.archive.gz"


def test_the_seven_newest_backups_are_kept(tmp_path):
    for day in range(1, 10):
        (tmp_path / f"scraped_data-202611{day:02d}T020000Z.archive.gz").touch()
    (tmp_path / "notes.txt").touch()

    removed = prune(tmp_path, "scraped_data")

    assert [p.name[13:21] for p in removed] == ["20261101", "20261102"]
    kept = sorted(p.name for p in tmp_path.glob("*.archive.gz"))
    assert len(kept) == 7 and kept[0].startswith("scraped_data-20261103")
    assert (tmp_path / "notes.txt").exists()


def test_a_failed_dump_raises_and_leaves_no_partial_file(tmp_path, monkeypatch):
    with pytest.raises(BackupError, match="status 2"):
        back_up(tmp_path, settings(monkeypatch), NOW, FakeTool(returncode=2))

    assert list(tmp_path.iterdir()) == []


def test_the_script_exits_non_zero_when_the_folder_is_missing(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(mongo_backup, "BACKUP_DIR", tmp_path / "missing")
    monkeypatch.setattr(mongo_backup.logfire, "configure", lambda: None)

    assert mongo_backup.main() == 1
    assert str(tmp_path / "missing") in capsys.readouterr().err
