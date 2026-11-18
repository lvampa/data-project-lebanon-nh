import pytest
from postgres import PostgresSettings
from pydantic import ValidationError
from sqlalchemy import make_url

ENVIRONMENT = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
)


@pytest.fixture
def empty_environment(monkeypatch):
    for variable in ENVIRONMENT:
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch


def test_defaults_cover_everything_but_the_password(empty_environment):
    empty_environment.setenv("POSTGRES_PASSWORD", "secret")

    url = PostgresSettings().url

    assert url.drivername == "postgresql+psycopg2"
    assert url.username == "app"
    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "app"


def test_a_missing_password_is_an_error_that_names_the_variable(empty_environment):
    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD"):
        PostgresSettings()


def test_url_keeps_password_with_url_delimiters(empty_environment):
    password = "p@ss/w:rd#1"
    empty_environment.setenv("POSTGRES_USER", "app")
    empty_environment.setenv("POSTGRES_PASSWORD", password)
    empty_environment.setenv("POSTGRES_HOST", "db.internal")
    empty_environment.setenv("POSTGRES_PORT", "6543")
    empty_environment.setenv("POSTGRES_DB", "lebanon")

    url = PostgresSettings().url
    reparsed = make_url(url.render_as_string(hide_password=False))

    assert reparsed.password == password
    assert reparsed.host == "db.internal"
    assert reparsed.port == 6543
    assert reparsed.database == "lebanon"
