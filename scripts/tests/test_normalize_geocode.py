"""The geocode job, with a scripted geocoder: no request ever leaves the machine."""

from datetime import datetime

import pytest
from locations.geocode import GeocodeResult, Precision
from postgres.lock import police_log_lock
from postgres.models.address_normalization import AddressNormalization
from sqlalchemy import select

from scripts.normalize import geocode as geocode_job

NOW = datetime(2026, 11, 13)

# Inside the city's bounds, and outside (Concord, NH).
IN_CITY = (43.6426, -72.2518)
CONCORD = (43.2081, -71.5376)


class FakeGeocoder:
    """Plays results by query; a query it does not know is a miss."""

    def __init__(self, results: dict[str, GeocodeResult | None] | None = None) -> None:
        self.results = results or {}
        self.queries: list[str] = []

    def __call__(self, query: str) -> GeocodeResult | None:
        self.queries.append(query)
        return self.results.get(query)


def hit(
    coordinates: tuple[float, float] = IN_CITY, precision: Precision = "exact"
) -> GeocodeResult:
    lat, lng = coordinates
    return GeocodeResult(lat, lng, precision)


def add_row(session, raw: str, **columns) -> None:
    values = {
        "normalized_address": raw.title(),
        "geocode_query": f"{raw}, Lebanon, NH",
        "kind": "address",
        "source": "ai",
        **columns,
    }
    session.add(
        AddressNormalization(raw_address=raw, created_at=NOW, updated_at=NOW, **values)
    )
    session.commit()


def the_row(session, raw: str) -> AddressNormalization:
    session.expire_all()
    row = session.scalar(
        select(AddressNormalization).where(AddressNormalization.raw_address == raw)
    )
    assert row is not None, raw
    return row


# --- placing a row ---


def test_a_matched_query_places_the_row_with_the_precision_the_geocoder_gave(
    db_session,
):
    add_row(db_session, "12 MAIN ST")
    geocoder = FakeGeocoder({"12 MAIN ST, Lebanon, NH": hit(precision="exact")})

    counts = geocode_job.run(geocoder)

    row = the_row(db_session, "12 MAIN ST")
    assert (row.lat, row.lng) == IN_CITY
    assert (row.geocoded_via, row.coordinate_precision) == ("nominatim", "exact")
    assert (counts.placed, counts.requests) == (1, 1)


def test_rule_rows_are_geocoded_too(db_session):
    add_row(db_session, "12 MAIN ST", source="rule")
    geocoder = FakeGeocoder({"12 MAIN ST, Lebanon, NH": hit()})

    geocode_job.run(geocoder)

    assert the_row(db_session, "12 MAIN ST").lat == IN_CITY[0]


def test_a_query_that_misses_falls_back_to_the_street_and_is_approximate(db_session):
    add_row(db_session, "12 MAIN ST", street="MAIN ST")
    geocoder = FakeGeocoder({"MAIN ST, Lebanon, NH": hit(precision="exact")})

    counts = geocode_job.run(geocoder)

    row = the_row(db_session, "12 MAIN ST")
    assert (row.lat, row.lng) == IN_CITY
    # A street matched without a point on it is approximate, whatever the match said.
    assert row.coordinate_precision == "approximate"
    assert geocoder.queries == ["12 MAIN ST, Lebanon, NH", "MAIN ST, Lebanon, NH"]
    assert counts.requests == 2


def test_a_result_outside_the_city_is_discarded_and_the_street_is_tried(db_session):
    add_row(db_session, "12 MAIN ST", street="MAIN ST")
    geocoder = FakeGeocoder(
        {"12 MAIN ST, Lebanon, NH": hit(CONCORD), "MAIN ST, Lebanon, NH": hit()}
    )

    geocode_job.run(geocoder)

    row = the_row(db_session, "12 MAIN ST")
    assert (row.lat, row.lng) == IN_CITY
    assert row.coordinate_precision == "approximate"


def test_a_street_result_outside_the_city_is_discarded_too(db_session):
    add_row(db_session, "12 MAIN ST", street="MAIN ST")
    geocoder = FakeGeocoder(
        {"12 MAIN ST, Lebanon, NH": hit(CONCORD), "MAIN ST, Lebanon, NH": hit(CONCORD)}
    )

    geocode_job.run(geocoder)

    row = the_row(db_session, "12 MAIN ST")
    assert (row.lat, row.lng, row.geocode_attempts) == (None, None, 1)


def test_a_row_with_no_geocode_query_is_looked_up_by_its_address(db_session):
    add_row(
        db_session, "HANNAFORDS", geocode_query=None, normalized_address="Hannaford"
    )
    geocoder = FakeGeocoder({"Hannaford, Lebanon, NH": hit()})

    geocode_job.run(geocoder)

    assert the_row(db_session, "HANNAFORDS").lat == IN_CITY[0]


# --- place codes (6.2) ---


def test_a_place_code_with_coordinates_on_another_row_is_reused_with_no_request(
    db_session,
):
    add_row(
        db_session,
        "HANNAFORDS - MARKET ST",
        place_code="L HANNAF",
        kind="place",
        lat=43.65,
        lng=-72.26,
        geocoded_via="nominatim",
        coordinate_precision="exact",
    )
    add_row(db_session, "HANNAFORDS MARKET", place_code="L HANNAF", kind="place")
    geocoder = FakeGeocoder()

    counts = geocode_job.run(geocoder)

    row = the_row(db_session, "HANNAFORDS MARKET")
    assert (row.lat, row.lng, row.geocoded_via) == (43.65, -72.26, "place_code")
    assert row.coordinate_precision == "exact"
    assert geocoder.queries == []
    assert (counts.reused, counts.requests) == (1, 0)


def test_a_place_code_with_no_coordinates_anywhere_is_looked_up_normally(db_session):
    add_row(db_session, "HANNAFORDS MARKET", place_code="L HANNAF", kind="place")
    geocoder = FakeGeocoder({"HANNAFORDS MARKET, Lebanon, NH": hit()})

    geocode_job.run(geocoder)

    assert the_row(db_session, "HANNAFORDS MARKET").geocoded_via == "nominatim"


# --- misses and attempts (6.5, 6.6) ---


def test_a_miss_counts_an_attempt_and_changes_nothing_else(db_session):
    add_row(db_session, "NOWHERE")

    counts = geocode_job.run(FakeGeocoder())

    row = the_row(db_session, "NOWHERE")
    assert (row.geocode_attempts, row.needs_review, row.lat) == (1, False, None)
    assert counts.missed == 1


def test_the_third_miss_gives_a_review_mark_and_the_row_is_not_tried_again(db_session):
    add_row(db_session, "NOWHERE")
    for _ in range(3):
        geocode_job.run(FakeGeocoder())
    again = FakeGeocoder()

    geocode_job.run(again)

    row = the_row(db_session, "NOWHERE")
    assert (row.geocode_attempts, row.needs_review) == (3, True)
    assert again.queries == []


# --- what is never geocoded ---


def test_a_bare_highway_is_marked_for_review_and_never_looked_up(db_session):
    add_row(
        db_session,
        "I-89 NB MM 18",
        kind="highway",
        normalized_address="I-89 northbound",
    )
    geocoder = FakeGeocoder()

    counts = geocode_job.run(geocoder)

    row = the_row(db_session, "I-89 NB MM 18")
    assert (row.needs_review, row.lat) == (True, None)
    assert geocoder.queries == []
    assert counts.bare_highways == 1


@pytest.mark.parametrize(
    "address",
    ["I-89 and Route 4", "I-89 exit 18", "I-89 & Main St"],
)
def test_a_highway_with_a_cross_street_or_exit_is_looked_up(db_session, address):
    add_row(
        db_session,
        "HWY",
        kind="highway",
        normalized_address=address,
        geocode_query=address,
    )
    geocoder = FakeGeocoder({address: hit(precision="approximate")})

    geocode_job.run(geocoder)

    assert the_row(db_session, "HWY").lat == IN_CITY[0]


def test_a_human_row_is_never_touched(db_session):
    add_row(db_session, "12 MAIN ST", source="human")

    geocoder = FakeGeocoder({"12 MAIN ST, Lebanon, NH": hit()})
    geocode_job.run(geocoder)

    assert geocoder.queries == []
    assert the_row(db_session, "12 MAIN ST").lat is None


def test_rows_that_already_have_coordinates_or_no_address_are_skipped(db_session):
    add_row(db_session, "PLACED", lat=43.6, lng=-72.2, geocoded_via="manual")
    add_row(
        db_session, "WAITING", normalized_address=None, geocode_query=None, source=None
    )
    geocoder = FakeGeocoder()

    geocode_job.run(geocoder)

    assert geocoder.queries == []


# --- the request budget (6.8) ---


def test_a_run_stops_at_the_request_limit_and_leaves_the_rest(db_session):
    for number in range(5):
        add_row(db_session, f"ROW {number}")
    geocoder = FakeGeocoder()

    counts = geocode_job.run(geocoder, max_requests=3)

    assert len(geocoder.queries) == 3
    assert counts.requests == 3
    assert counts.stopped_at_limit is True
    untouched = [the_row(db_session, f"ROW {n}").geocode_attempts for n in range(5)]
    assert untouched == [1, 1, 1, 0, 0]


def test_the_default_limit_is_six_hundred_requests():
    assert geocode_job.MAX_REQUESTS == 600


# --- the command ---


def test_the_command_places_rows_and_exits_zero(db_session, capsys):
    add_row(db_session, "12 MAIN ST")
    geocoder = FakeGeocoder({"12 MAIN ST, Lebanon, NH": hit()})

    status = geocode_job.main([], geocoder=geocoder)

    assert status == 0
    assert "1 placed" in capsys.readouterr().out


def test_another_police_log_job_running_stops_the_command(
    db_session, test_engine, capsys
):
    add_row(db_session, "12 MAIN ST")
    geocoder = FakeGeocoder({"12 MAIN ST, Lebanon, NH": hit()})

    with police_log_lock(test_engine) as acquired:
        assert acquired
        status = geocode_job.main([], geocoder=geocoder)

    assert status == 1
    assert geocoder.queries == []
    assert "Another police log job is running" in capsys.readouterr().err


def test_the_lock_is_released_when_the_command_ends(db_session, test_engine):
    geocode_job.main([], geocoder=FakeGeocoder())

    with police_log_lock(test_engine) as acquired:
        assert acquired


def test_help_prints_usage_and_never_runs_the_job(db_session, capsys):
    geocoder = FakeGeocoder({"12 MAIN ST, Lebanon, NH": hit()})
    add_row(db_session, "12 MAIN ST")

    with pytest.raises(SystemExit) as stopped:
        geocode_job.main(["--help"], geocoder=geocoder)

    assert stopped.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()
    assert geocoder.queries == []
    assert the_row(db_session, "12 MAIN ST").lat is None


def test_an_unknown_argument_is_refused_and_never_runs_the_job(db_session):
    geocoder = FakeGeocoder()

    with pytest.raises(SystemExit):
        geocode_job.main(["--everything"], geocoder=geocoder)

    assert geocoder.queries == []
