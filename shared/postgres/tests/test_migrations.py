import pytest
from alembic import command
from alembic.config import Config
from postgres_testing.plugin import ALEMBIC_INI
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def alembic_config(db_connection):
    # Alembic joins the test's connection, so every step is rolled back with it.
    config = Config(ALEMBIC_INI)
    config.attributes["connection"] = db_connection
    return config


def test_migrations_run_up_and_down_and_match_models(alembic_config):
    command.downgrade(alembic_config, "base")

    command.upgrade(alembic_config, "head")
    command.check(alembic_config)
    command.downgrade(alembic_config, "base")


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO llcs (name, lookup_status, created_at)"
        " VALUES ('X LLC', 'bogus', now())",
        "INSERT INTO budget_documents (fiscal_year, document_type, source_url, scraped_at)"
        " VALUES (2026, 'bogus', 'https://example.com', now())",
        "INSERT INTO address_normalizations (raw_address, geocoded_via, created_at, updated_at)"
        " VALUES ('1 MAIN ST', 'bogus', now(), now())",
        "INSERT INTO planning_documents (civicclerk_file_id, civicclerk_event_id, scraped_at)"
        " VALUES (1, 999, now())",
        "INSERT INTO pdf_urls (canonical_url, state, created_at)"
        " VALUES ('https://example.com/a.pdf', 'bogus', now())",
    ],
    ids=[
        "lookup_status",
        "document_type",
        "geocoded_via",
        "planning_event_fk",
        "pdf_url_state",
    ],
)
def test_constraints_reject_invalid_rows(db_connection, statement):
    with pytest.raises(IntegrityError):
        db_connection.execute(text(statement))


def test_the_osm_migration_resets_osm_pins_on_the_way_down(
    alembic_config, db_connection
):
    command.upgrade(alembic_config, "head")
    db_connection.execute(
        text(
            "INSERT INTO address_normalizations (raw_address, lat, lng, geocoded_via,"
            " coordinate_precision, osm_ref, geocode_source_url, source, created_at,"
            " updated_at)"
            " VALUES ('A', 43.6, -72.2, 'osm', 'exact', 'way/1', NULL, 'ai', now(), now()),"
            " ('B', 43.7, -72.3, 'manual', 'exact', NULL, NULL, 'human', now(), now()),"
            " ('C', 43.8, -72.4, 'research', 'exact', NULL, 'https://example.com/p',"
            " 'ai', now(), now())"
        )
    )

    command.downgrade(alembic_config, "d74f0b2e8a51")

    rows = db_connection.execute(
        text(
            "SELECT raw_address, lat, geocoded_via, coordinate_precision"
            " FROM address_normalizations ORDER BY raw_address"
        )
    ).all()
    assert [tuple(r) for r in rows] == [
        ("A", None, None, None),
        ("B", 43.7, "manual", "exact"),
        ("C", None, None, None),
    ]
    columns = db_connection.execute(
        text(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'address_normalizations'"
        )
    ).scalars()
    assert not {"osm_ref", "geocode_source_url"} & set(columns)


def test_the_names_person_migration_defaults_existing_rows_to_false(
    alembic_config, db_connection
):
    command.downgrade(alembic_config, "f3b8d1a47c92")
    db_connection.execute(
        text(
            "INSERT INTO address_normalizations (raw_address, source, created_at,"
            " updated_at) VALUES ('A', 'ai', now(), now())"
        )
    )

    command.upgrade(alembic_config, "head")

    flag = db_connection.execute(
        text("SELECT names_person FROM address_normalizations WHERE raw_address = 'A'")
    ).scalar_one()
    assert flag is False
    command.downgrade(alembic_config, "f3b8d1a47c92")
    columns = db_connection.execute(
        text(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'address_normalizations'"
        )
    ).scalars()
    assert "names_person" not in list(columns)
    command.upgrade(alembic_config, "head")
