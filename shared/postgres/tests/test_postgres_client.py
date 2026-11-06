from postgres.client import _build_url
from sqlalchemy import make_url


def test_build_url_defaults(monkeypatch):
    for var in (
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
    ):
        monkeypatch.delenv(var, raising=False)

    url = _build_url()

    assert url.drivername == "postgresql+psycopg2"
    assert url.username == "app"
    assert url.password == "app"
    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "app"


def test_build_url_keeps_password_with_url_delimiters(monkeypatch):
    password = "p@ss/w:rd#1"
    monkeypatch.setenv("POSTGRES_USER", "app")
    monkeypatch.setenv("POSTGRES_PASSWORD", password)
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    monkeypatch.setenv("POSTGRES_DB", "lebanon")

    url = _build_url()
    reparsed = make_url(url.render_as_string(hide_password=False))

    assert reparsed.password == password
    assert reparsed.host == "db.internal"
    assert reparsed.port == 6543
    assert reparsed.database == "lebanon"
