"""The R2 settings go to the command's environment only."""

import os
import sys
from types import SimpleNamespace

import pytest

from dags.publish import r2_env, run_with_r2


def connection(**overrides):
    values = {
        "login": "key-id",
        "password": "key-secret",
        "extra_dejson": {"endpoint_url": "https://acct.example.test", "bucket": "data"},
        **overrides,
    }
    return SimpleNamespace(**values)


def test_the_env_is_built_from_the_connection():
    assert r2_env(connection()) == {
        "AWS_ACCESS_KEY_ID": "key-id",
        "AWS_SECRET_ACCESS_KEY": "key-secret",
        "R2_ENDPOINT": "https://acct.example.test",
        "R2_BUCKET": "data",
    }


@pytest.mark.parametrize(
    ("overrides", "name"),
    [
        ({"login": None}, "AWS_ACCESS_KEY_ID"),
        ({"password": ""}, "AWS_SECRET_ACCESS_KEY"),
        ({"extra_dejson": {"bucket": "data"}}, "R2_ENDPOINT"),
        ({"extra_dejson": {"endpoint_url": "https://e.test"}}, "R2_BUCKET"),
    ],
)
def test_a_missing_field_is_named_and_no_value_is_printed(overrides, name):
    with pytest.raises(ValueError, match=name) as raised:
        r2_env(connection(**overrides))
    assert "key-secret" not in str(raised.value)


def test_the_command_sees_the_settings_and_this_process_does_not(tmp_path, caplog):
    out = tmp_path / "seen.txt"
    script = (
        f"import os; open({str(out)!r}, 'w').write(os.environ['R2_BUCKET'] + ' ' + "
        "os.environ['AWS_SECRET_ACCESS_KEY'])"
    )

    run_with_r2([sys.executable, "-c", script], str(tmp_path), connection())

    assert out.read_text() == "data key-secret"
    assert "R2_BUCKET" not in os.environ
    assert "AWS_SECRET_ACCESS_KEY" not in os.environ


def test_a_failing_command_raises_without_the_secret(tmp_path):
    with pytest.raises(Exception) as raised:
        run_with_r2(
            [sys.executable, "-c", "raise SystemExit(3)"], str(tmp_path), connection()
        )
    assert "key-secret" not in str(raised.value)
