import pytest
from postgres.client import SessionLocal, engine
from postgres.models.pdf_url import PdfUrl
from postgres_testing.plugin import is_test_database
from sqlalchemy import func, select, text
from sqlalchemy.exc import UnboundExecutionError


@pytest.mark.parametrize(
    ("name", "expected"),
    [("app_test", True), ("scratch_test", True), ("app", False), ("test_app", False)],
)
def test_only_names_ending_in_test_count_as_test_databases(name, expected):
    assert is_test_database(name) is expected


def test_engine_points_at_the_test_database():
    assert is_test_database(engine.url.database)


def test_schema_is_built_by_the_migrations(db_session):
    version = db_session.execute(text("SELECT version_num FROM alembic_version"))

    assert version.scalar_one()


def _add_pdf_url(session) -> None:
    session.execute(
        text(
            "INSERT INTO pdf_urls (canonical_url, created_at)"
            " VALUES ('https://example.com/a.pdf', now())"
        )
    )


def test_committed_rows_are_visible_to_other_sessions_in_the_test(db_session):
    with SessionLocal() as writer:
        _add_pdf_url(writer)
        writer.commit()

    assert db_session.scalar(select(func.count()).select_from(PdfUrl)) == 1


def test_commits_never_reach_the_database(db_session):
    _add_pdf_url(db_session)
    db_session.commit()

    with engine.connect() as outside:
        assert outside.scalar(select(func.count()).select_from(PdfUrl)) == 0


def test_rollback_in_code_under_test_keeps_earlier_commits(db_session):
    _add_pdf_url(db_session)
    db_session.commit()

    db_session.execute(text("DELETE FROM pdf_urls"))
    db_session.rollback()

    assert db_session.scalar(select(func.count()).select_from(PdfUrl)) == 1


def test_session_without_the_fixture_has_no_database():
    # Last in the file on purpose: it also shows the fixture unbinds on teardown.
    with SessionLocal() as session, pytest.raises(UnboundExecutionError):
        session.execute(text("SELECT 1"))
