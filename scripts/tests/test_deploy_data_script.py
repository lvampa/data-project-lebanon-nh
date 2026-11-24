"""The credential checks in deploy-data.sh, which run before any export or upload."""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
SCRIPT = "scripts/deploy-data.sh"


def run(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    # A clean environment, so the caller's own R2 or AWS settings cannot change the result.
    clean = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/"), **env}
    return subprocess.run(
        ["bash", SCRIPT, *args],
        cwd=REPO_ROOT,
        env=clean,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({}, "R2_BUCKET is not set"),
        ({"R2_BUCKET": "b"}, "set R2_ENDPOINT or CLOUDFLARE_ACCOUNT_ID"),
        (
            {"R2_BUCKET": "b", "CLOUDFLARE_ACCOUNT_ID": "a"},
            "set AWS_PROFILE, or both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY",
        ),
        (
            {
                "R2_BUCKET": "b",
                "R2_ENDPOINT": "https://e.test",
                "AWS_ACCESS_KEY_ID": "k",
            },
            "set AWS_PROFILE, or both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY",
        ),
        (
            {
                "R2_BUCKET": "b",
                "R2_ENDPOINT": "https://e.test",
                "AWS_SECRET_ACCESS_KEY": "s",
            },
            "set AWS_PROFILE, or both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY",
        ),
    ],
)
def test_the_upload_stops_before_the_export_without_a_complete_setup(env, message):
    result = run(**env)
    assert result.returncode == 1
    assert message in result.stderr
    assert "Exporting" not in result.stdout


BUCKET = {"R2_BUCKET": "b", "R2_ENDPOINT": "https://e.test"}


@pytest.mark.parametrize(
    ("env", "message"),
    [
        (
            {
                **BUCKET,
                "AWS_PROFILE": "p",
                "AWS_ACCESS_KEY_ID": "k",
                "AWS_SECRET_ACCESS_KEY": "s",
            },
            "set AWS_PROFILE or the key pair, not both",
        ),
        (
            {**BUCKET, "AWS_ACCESS_KEY_ID": "None", "AWS_SECRET_ACCESS_KEY": "None"},
            "set AWS_PROFILE, or both",
        ),
        (
            {**BUCKET, "AWS_ACCESS_KEY_ID": "", "AWS_SECRET_ACCESS_KEY": ""},
            "set AWS_PROFILE, or both",
        ),
        (
            {"R2_BUCKET": "None", "R2_ENDPOINT": "https://e.test"},
            "R2_BUCKET is not set",
        ),
        (
            {"R2_BUCKET": "b", "R2_ENDPOINT": "None"},
            "set R2_ENDPOINT or CLOUDFLARE_ACCOUNT_ID",
        ),
        ({**BUCKET, "AWS_PROFILE": "None"}, "set AWS_PROFILE, or both"),
    ],
)
def test_a_missing_none_or_doubled_credential_is_refused(env, message):
    result = run(**env)
    assert result.returncode == 1
    assert message in result.stderr
    assert "Holding" not in result.stdout


def test_the_error_never_prints_a_credential():
    result = run(R2_BUCKET="b", AWS_SECRET_ACCESS_KEY="zz-secret-value")
    assert "zz-secret-value" not in result.stdout + result.stderr


def test_an_unknown_argument_is_refused():
    result = run("--nope")
    assert result.returncode == 1
    assert "unknown argument" in result.stderr
