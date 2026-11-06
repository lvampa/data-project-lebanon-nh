import pytest

from api.config import Settings

ENV_VARS = [
    "ELASTICSEARCH_HOST",
    "CORS_ORIGINS",
    "ADMIN_API_TOKEN",
    "NOMINATIM_CONTACT",
]


@pytest.fixture
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_defaults_when_env_is_unset(clean_env):
    settings = Settings()

    assert settings.elasticsearch_host == "http://localhost:9200"
    assert settings.cors_origins == ["http://localhost:3001"]
    assert settings.admin_api_token is None
    assert settings.nominatim_contact is None


def test_cors_origins_splits_on_commas(clean_env):
    clean_env.setenv("CORS_ORIGINS", "a,b")

    assert Settings().cors_origins == ["a", "b"]


def test_reads_values_from_env(clean_env):
    clean_env.setenv("ELASTICSEARCH_HOST", "http://es:9200")
    clean_env.setenv("ADMIN_API_TOKEN", "secret")
    clean_env.setenv("NOMINATIM_CONTACT", "ops@example.com")

    settings = Settings()

    assert settings.elasticsearch_host == "http://es:9200"
    assert settings.admin_api_token == "secret"
    assert settings.nominatim_contact == "ops@example.com"
