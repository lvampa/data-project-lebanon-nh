from datetime import datetime

import pytest
from alembic import command
from alembic.config import Config
from postgres.models.address_normalization import AddressNormalization
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres_testing.plugin import ALEMBIC_INI
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

NOW = datetime(2026, 11, 13)

# The revision before the provenance columns.
BEFORE_PROVENANCE = "7c4d2b19a8e3"


def add_category(session, **columns) -> IncidentTypeCategory:
    row = IncidentTypeCategory(
        raw_incident_type=columns.pop("raw_incident_type", "MV COMPLAINT"),
        created_at=NOW,
        updated_at=NOW,
        **columns,
    )
    session.add(row)
    session.commit()
    return row


def add_address(session, **columns) -> AddressNormalization:
    row = AddressNormalization(
        raw_address=columns.pop("raw_address", "12 MAIN ST"),
        created_at=NOW,
        updated_at=NOW,
        **columns,
    )
    session.add(row)
    session.commit()
    return row


# --- a value that is still waiting ---


def test_a_raw_incident_type_can_wait_with_no_category_and_no_source(db_session):
    row = add_category(db_session)

    assert (row.category, row.normalized_type, row.source) == (None, None, None)
    assert (row.needs_review, row.failed_attempts) == (False, 0)
    assert (row.prompt_version, row.ai_call_id) == (None, None)


def test_a_raw_address_can_wait_with_nothing_but_its_raw_value(db_session):
    row = add_address(db_session)

    assert (row.kind, row.source, row.normalized_address) == (None, None, None)
    assert (row.needs_review, row.failed_attempts, row.geocode_attempts) == (
        False,
        0,
        0,
    )


# --- the source check ---


@pytest.mark.parametrize("source", ["rule", "ai", "human"])
def test_the_three_sources_are_accepted_on_both_tables(db_session, source):
    add_category(db_session, raw_incident_type=f"type {source}", source=source)
    add_address(db_session, raw_address=f"addr {source}", source=source)


@pytest.mark.parametrize(
    "table",
    ["incident_type_categories", "address_normalizations"],
)
def test_an_unknown_source_is_rejected(db_connection, table):
    key = "raw_incident_type" if table == "incident_type_categories" else "raw_address"

    with pytest.raises(IntegrityError):
        db_connection.execute(
            text(
                f"INSERT INTO {table} ({key}, source, created_at, updated_at)"
                " VALUES ('x', 'robot', now(), now())"
            )
        )


# --- the location columns ---


@pytest.mark.parametrize("kind", ["address", "intersection", "place", "highway"])
def test_the_four_location_kinds_are_accepted(db_session, kind):
    add_address(db_session, kind=kind)


def test_an_unknown_location_kind_is_rejected(db_connection):
    with pytest.raises(IntegrityError):
        db_connection.execute(
            text(
                "INSERT INTO address_normalizations (raw_address, kind, created_at, updated_at)"
                " VALUES ('x', 'landmark', now(), now())"
            )
        )


@pytest.mark.parametrize("precision", ["exact", "approximate"])
def test_both_coordinate_precisions_are_accepted(db_session, precision):
    add_address(db_session, coordinate_precision=precision)


def test_an_unknown_coordinate_precision_is_rejected(db_connection):
    with pytest.raises(IntegrityError):
        db_connection.execute(
            text(
                "INSERT INTO address_normalizations"
                " (raw_address, coordinate_precision, created_at, updated_at)"
                " VALUES ('x', 'roughly', now(), now())"
            )
        )


@pytest.mark.parametrize("via", ["manual", "nominatim", "place_code"])
def test_geocoded_via_accepts_place_code_beside_the_old_two(db_session, via):
    add_address(db_session, geocoded_via=via)


def test_a_row_keeps_its_place_code_street_and_geocode_query(db_session):
    row = add_address(
        db_session,
        place_code="L HANNAF",
        street="MARKET ST",
        geocode_query="Hannaford, Market St, Lebanon, NH",
    )

    db_session.expire_all()
    assert (row.place_code, row.street, row.geocode_query) == (
        "L HANNAF",
        "MARKET ST",
        "Hannaford, Market St, Lebanon, NH",
    )


# --- the migration over rows that already exist ---


@pytest.fixture
def alembic_config(db_connection):
    config = Config(ALEMBIC_INI)
    config.attributes["connection"] = db_connection
    return config


def test_rows_from_before_the_columns_existed_become_human_rows(
    db_connection, alembic_config
):
    command.downgrade(alembic_config, BEFORE_PROVENANCE)
    db_connection.execute(
        text(
            "INSERT INTO incident_type_categories"
            " (raw_incident_type, category, subcategory, created_at, updated_at)"
            " VALUES ('NOISE', 'Police', 'Noise', now(), now())"
        )
    )
    db_connection.execute(
        text(
            "INSERT INTO address_normalizations"
            " (raw_address, normalized_address, lat, lng, geocoded_via, created_at, updated_at)"
            " VALUES ('12 MAIN ST', '12 Main St', 43.64, -72.25, 'manual', now(), now()),"
            "        ('34 ELM ST', NULL, NULL, NULL, NULL, now(), now())"
        )
    )

    command.upgrade(alembic_config, "head")

    # Nothing before this work was an AI or rule answer, so a later AI run must not
    # overwrite what is there.
    assert db_connection.execute(
        text("SELECT source, category FROM incident_type_categories")
    ).all() == [("human", "Police")]
    sources = dict(
        db_connection.execute(
            text("SELECT raw_address, source FROM address_normalizations")
        ).all()
    )
    assert sources == {"12 MAIN ST": "human", "34 ELM ST": None}


def test_the_subcategory_column_is_gone_and_comes_back_empty_on_downgrade(
    db_connection, alembic_config
):
    def columns() -> set[str]:
        return {
            row[0]
            for row in db_connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_name = 'incident_type_categories'"
                )
            )
        }

    command.upgrade(alembic_config, "head")
    assert "subcategory" not in columns()
    assert "normalized_type" in columns()

    command.downgrade(alembic_config, BEFORE_PROVENANCE)
    assert "subcategory" in columns()
    assert "normalized_type" not in columns()
