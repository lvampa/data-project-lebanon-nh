from postgres import get_postgres_settings

from api.config import get_settings


def test_api_and_postgres_read_the_same_postgres_settings():
    assert get_settings().postgres is get_postgres_settings()
