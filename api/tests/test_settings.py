from postgres import get_postgres_settings

from api.deps import get_session


def test_api_sessions_use_the_shared_postgres_settings(db_connection):
    session = next(get_session())
    try:
        assert session.get_bind().engine.url == get_postgres_settings().url
    finally:
        session.close()
