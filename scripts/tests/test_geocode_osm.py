"""The OpenStreetMap step of the geocode job, with a fixture snapshot, a scripted
geocoder and a scripted AI. Nothing here touches the network."""

import csv
from datetime import datetime

import pytest
from locations.geocode import GeocodeResult
from locations.osm import Candidate, snapshot_from_replies
from postgres.models.address_normalization import AddressNormalization
from sqlalchemy import select

from scripts.normalize import geocode as geocode_job
from scripts.normalize.backends import (
    AiBackendUnavailable,
    AiCallFailed,
    FakeBackend,
)
from scripts.normalize.csv_cells import cell, uncell
from scripts.normalize.match_review import Placed, write_review
from scripts.normalize.osm_locate import OsmLocator
from scripts.normalize.place_match import pick_candidate, place_match_prompt

NOW = datetime(2026, 11, 20)
STREET_POINT = (43.6740, -72.2656)


def way(way_id: int, name: str, *nodes: tuple[int, float, float]) -> dict:
    return {
        "type": "way",
        "id": way_id,
        "tags": {"highway": "residential", "name": name},
        "nodes": [n[0] for n in nodes],
        "geometry": [{"lat": n[1], "lon": n[2]} for n in nodes],
    }


SNAPSHOT = snapshot_from_replies(
    "2026-11-20",
    {
        "elements": [
            {
                "type": "way",
                "id": 10,
                "center": {"lat": 43.6501, "lon": -72.2480},
                "tags": {
                    "addr:housenumber": "8",
                    "addr:street": "Commerce Avenue",
                    "building": "yes",
                },
            },
            {
                "type": "node",
                "id": 11,
                "lat": 43.6745,
                "lon": -72.2640,
                "tags": {"name": "Quarry Hill Town Houses", "building": "apartments"},
            },
            {
                "type": "node",
                "id": 12,
                "lat": 43.6746,
                "lon": -72.2655,
                "tags": {"name": "Quarry Hill Marketing"},
            },
        ]
    },
    {
        "elements": [
            way(1, "Mount Support Road", (1, 43.674, -72.27), (2, 43.674, -72.265)),
            way(2, "Dartmouth Avenue", (4, 43.670, -72.265), (2, 43.674, -72.265)),
            way(3, "Commerce Avenue", (5, 43.650, -72.250), (6, 43.650, -72.245)),
        ]
    },
)


class NoNominatim:
    """A geocoder that knows nothing, and remembers what it was asked."""

    def __init__(self, results: dict[str, GeocodeResult] | None = None) -> None:
        self.results = results or {}
        self.queries: list[str] = []

    def __call__(self, query: str) -> GeocodeResult | None:
        self.queries.append(query)
        return self.results.get(query)


class Picks:
    """A picker that plays one answer per call: a candidate index, None, or an error."""

    def __init__(self, *answers: int | None | Exception) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, str, list[str]]] = []

    def __call__(self, name: str, street: str, candidates) -> Candidate | None:
        self.calls.append((name, street, [c.feature.ref for c in candidates]))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return None if answer is None else candidates[answer]


def add_row(session, raw: str, **columns) -> AddressNormalization:
    values = {
        "normalized_address": raw.title(),
        "geocode_query": f"{raw}, Lebanon, NH",
        "kind": "address",
        "source": "ai",
        **columns,
    }
    row = AddressNormalization(
        raw_address=raw, created_at=NOW, updated_at=NOW, **values
    )
    session.add(row)
    session.commit()
    return row


def the_row(session, raw: str) -> AddressNormalization:
    session.expire_all()
    return session.scalars(
        select(AddressNormalization).where(AddressNormalization.raw_address == raw)
    ).one()


def approximate(**columns) -> dict:
    return {
        "lat": STREET_POINT[0],
        "lng": STREET_POINT[1],
        "coordinate_precision": "approximate",
        "geocoded_via": "nominatim",
        **columns,
    }


# --- placing a new row from the snapshot ---


def test_a_house_address_is_placed_from_the_snapshot_after_nominatim_misses(db_session):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
    )
    geocoder = NoNominatim()
    locator = OsmLocator(SNAPSHOT)

    counts = geocode_job.run(geocoder, locator=locator)

    row = the_row(db_session, "8 COMMERCE AVE")
    assert (row.lat, row.lng) == (43.6501, -72.2480)
    assert (row.geocoded_via, row.coordinate_precision, row.osm_ref) == (
        "osm",
        "exact",
        "way/10",
    )
    # Only the row's own query went to Nominatim. The street was never asked for.
    assert geocoder.queries == ["8 COMMERCE AVE, Lebanon, NH"]
    assert counts.found_by() == {"address": 1}


def test_nominatim_comes_first_and_a_hit_skips_the_snapshot(db_session):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
    )
    geocoder = NoNominatim(
        {"8 COMMERCE AVE, Lebanon, NH": GeocodeResult(43.6, -72.2, "exact")}
    )

    counts = geocode_job.run(geocoder, locator=OsmLocator(SNAPSHOT))

    assert the_row(db_session, "8 COMMERCE AVE").geocoded_via == "nominatim"
    assert counts.from_snapshot == []


def test_an_intersection_is_placed_at_the_node_its_roads_share(db_session):
    add_row(
        db_session,
        "MT SUPPORT RD & DARTMOUTH AVE",
        kind="intersection",
        normalized_address="Mount Support Rd and Dartmouth Ave",
        street="MOUNT SUPPORT RD",
    )

    counts = geocode_job.run(NoNominatim(), locator=OsmLocator(SNAPSHOT))

    row = the_row(db_session, "MT SUPPORT RD & DARTMOUTH AVE")
    assert (row.lat, row.lng, row.osm_ref) == (43.674, -72.265, "node/2")
    assert counts.found_by() == {"intersection": 1}


def test_a_miss_in_the_snapshot_falls_back_to_the_street(db_session):
    add_row(
        db_session,
        "9 COMMERCE AVE",
        normalized_address="9 Commerce Ave",
        street="COMMERCE AVE",
    )
    geocoder = NoNominatim(
        {"COMMERCE AVE, Lebanon, NH": GeocodeResult(43.65, -72.25, "exact")}
    )

    geocode_job.run(geocoder, locator=OsmLocator(SNAPSHOT))

    row = the_row(db_session, "9 COMMERCE AVE")
    assert (row.geocoded_via, row.coordinate_precision, row.osm_ref) == (
        "nominatim",
        "approximate",
        None,
    )


def place_row(
    session,
    raw: str = "QUARRY HILL TOWN HOUSES",
    name: str = "Quarry Hill Town Houses",
    **columns,
):
    return add_row(
        session,
        raw,
        **{
            "kind": "place",
            "normalized_address": f"{name}, Mount Support Rd",
            "street": "MOUNT SUPPORT RD",
            **columns,
        },
    )


def test_a_named_place_goes_to_the_ai_with_its_candidates_and_takes_its_pick(
    db_session,
):
    place_row(db_session)
    picks = Picks(0)

    counts = geocode_job.run(NoNominatim(), locator=OsmLocator(SNAPSHOT, picks))

    row = the_row(db_session, "QUARRY HILL TOWN HOUSES")
    assert (row.lat, row.lng, row.osm_ref) == (43.6745, -72.2640, "node/11")
    assert picks.calls == [
        ("Quarry Hill Town Houses", "MOUNT SUPPORT RD", ["node/11", "node/12"])
    ]
    assert counts.found_by() == {"llm": 1}


def test_a_none_from_the_ai_leaves_the_street_fallback(db_session):
    place_row(db_session)
    geocoder = NoNominatim(
        {"MOUNT SUPPORT RD, Lebanon, NH": GeocodeResult(*STREET_POINT, "exact")}
    )

    geocode_job.run(geocoder, locator=OsmLocator(SNAPSHOT, Picks(None)))

    row = the_row(db_session, "QUARRY HILL TOWN HOUSES")
    assert (row.coordinate_precision, row.osm_ref) == ("approximate", None)


def test_a_failed_ai_call_is_a_miss_and_the_run_goes_on(db_session):
    place_row(db_session)
    locator = OsmLocator(SNAPSHOT, Picks(AiCallFailed("bad answer")))

    geocode_job.run(NoNominatim(), locator=locator)

    assert the_row(db_session, "QUARRY HILL TOWN HOUSES").lat is None
    assert not locator.llm_stopped


def test_a_stopped_backend_ends_the_ai_calls_and_counts_what_was_left(db_session):
    place_row(db_session, "QUARRY HILL TOWN HOUSES")
    place_row(db_session, "QUARRY HILL MARKETING", "Quarry Hill Marketing")
    picks = Picks(AiBackendUnavailable("logged out"))
    locator = OsmLocator(SNAPSHOT, picks)

    geocode_job.run(NoNominatim(), locator=locator)

    assert len(picks.calls) == 1
    assert (locator.llm_stopped, locator.left_for_next_run) == (True, 2)


def test_the_ai_call_cap_leaves_the_rest_for_the_next_run(db_session):
    place_row(db_session, "QUARRY HILL TOWN HOUSES")
    place_row(db_session, "QUARRY HILL MARKETING", "Quarry Hill Marketing")
    picks = Picks(0, 0)
    locator = OsmLocator(SNAPSHOT, picks, max_llm_calls=1)

    geocode_job.run(NoNominatim(), locator=locator)

    assert (locator.llm_calls, locator.left_for_next_run) == (1, 1)


def test_with_no_ai_a_place_is_left_alone_and_nothing_is_counted_as_left(db_session):
    place_row(db_session)
    locator = OsmLocator(SNAPSHOT)

    geocode_job.run(NoNominatim(), locator=locator)

    assert the_row(db_session, "QUARRY HILL TOWN HOUSES").lat is None
    assert (locator.llm_calls, locator.left_for_next_run) == (0, 0)


def test_a_place_with_no_candidate_makes_no_ai_call(db_session):
    place_row(db_session, "NOWHERE SPECIAL", "Nowhere Special")
    picks = Picks()

    geocode_job.run(NoNominatim(), locator=OsmLocator(SNAPSHOT, picks))

    assert picks.calls == []


def test_a_bare_street_is_never_matched_to_a_feature(db_session):
    add_row(
        db_session,
        "MT SUPPORT RD",
        kind="place",
        normalized_address="Mount Support Rd",
        street="MOUNT SUPPORT RD",
    )
    picks = Picks()

    geocode_job.run(NoNominatim(), locator=OsmLocator(SNAPSHOT, picks))

    assert picks.calls == []


# --- --retry-approximate ---


def test_the_retry_places_an_approximate_row_and_charges_no_nominatim_request(
    db_session,
):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
        **approximate(),
    )

    counts = geocode_job.run_retry(OsmLocator(SNAPSHOT))

    row = the_row(db_session, "8 COMMERCE AVE")
    assert (row.lat, row.coordinate_precision, row.geocoded_via, row.osm_ref) == (
        43.6501,
        "exact",
        "osm",
        "way/10",
    )
    assert (counts.placed, counts.requests, counts.groups_kept) == (1, 0, 0)
    [placed] = counts.from_snapshot
    assert (placed.old_lat, placed.old_precision) == (STREET_POINT[0], "approximate")


def test_a_miss_in_the_retry_changes_nothing(db_session):
    add_row(
        db_session,
        "9 COMMERCE AVE",
        normalized_address="9 Commerce Ave",
        street="COMMERCE AVE",
        **approximate(),
    )

    counts = geocode_job.run_retry(OsmLocator(SNAPSHOT))

    row = the_row(db_session, "9 COMMERCE AVE")
    assert (row.lat, row.coordinate_precision, row.geocode_attempts) == (
        STREET_POINT[0],
        "approximate",
        0,
    )
    assert (row.needs_review, counts.groups_kept) == (False, 1)


def test_one_lookup_places_every_spelling_in_a_group(db_session):
    for raw in ("8 COMMERCE AVE", "8 COMMERCE AV"):
        add_row(
            db_session,
            raw,
            normalized_address="8 Commerce Ave",
            street="COMMERCE AVE",
            **approximate(),
        )

    counts = geocode_job.run_retry(OsmLocator(SNAPSHOT))

    assert the_row(db_session, "8 COMMERCE AVE").osm_ref == "way/10"
    assert the_row(db_session, "8 COMMERCE AV").osm_ref == "way/10"
    assert (counts.placed, counts.groups_retried) == (2, 1)


def test_a_group_with_a_human_row_is_left_alone(db_session):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
        **approximate(),
    )
    add_row(
        db_session,
        "8 COMMERCE AV",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
        source="human",
        lat=43.6,
        lng=-72.2,
        coordinate_precision="exact",
        geocoded_via="manual",
    )

    counts = geocode_job.run_retry(OsmLocator(SNAPSHOT))

    assert the_row(db_session, "8 COMMERCE AVE").lat == STREET_POINT[0]
    human = the_row(db_session, "8 COMMERCE AV")
    assert (human.lat, human.geocoded_via, human.source) == (43.6, "manual", "human")
    assert counts.groups_kept == 1


def test_rows_that_share_a_place_code_are_one_group(db_session):
    place_row(
        db_session, "QUARRY HILL TOWN HOUSES", place_code="Q HILL", **approximate()
    )
    add_row(
        db_session,
        "Q HILL TH",
        kind="place",
        normalized_address="Quarry Hill Townhouses, Mount Support Rd",
        street="MOUNT SUPPORT RD",
        place_code="Q HILL",
        **approximate(),
    )
    picks = Picks(0)

    counts = geocode_job.run_retry(OsmLocator(SNAPSHOT, picks))

    assert len(picks.calls) == 1
    assert the_row(db_session, "Q HILL TH").osm_ref == "node/11"
    assert (counts.placed, counts.groups_retried) == (2, 1)


def test_an_exact_row_is_not_retried(db_session):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
        lat=43.6,
        lng=-72.2,
        coordinate_precision="exact",
        geocoded_via="nominatim",
    )

    counts = geocode_job.run_retry(OsmLocator(SNAPSHOT))

    assert the_row(db_session, "8 COMMERCE AVE").lat == 43.6
    assert counts.groups_retried == 0


# --- the review file ---


def placed_item(name: str = "Shop") -> Placed:
    match = OsmLocator(SNAPSHOT).locate(
        AddressNormalization(
            raw_address="8 COMMERCE AVE",
            normalized_address="8 Commerce Ave",
            kind="address",
        )
    )
    assert match is not None
    return Placed("8 COMMERCE AVE", name, match, 43.65, -72.25, "approximate")


def test_the_review_file_records_old_and_new_coordinates(tmp_path):
    path = write_review([placed_item()], tmp_path, NOW)

    assert path is not None and path.name == "geocode-matches-20261120-0000.csv"
    [row] = list(csv.DictReader(path.open()))
    assert (row["found_by"], row["osm_ref"], row["was_approximate"]) == (
        "address",
        "way/10",
        "True",
    )
    assert (row["old_lat"], row["old_lng"], row["old_precision"]) == (
        "43.65",
        "-72.25",
        "approximate",
    )
    assert (row["new_lat"], row["new_lng"], row["new_precision"]) == (
        "43.6501",
        "-72.248",
        "exact",
    )
    assert int(row["meters_moved"]) > 0


def test_no_placements_write_no_file(tmp_path):
    assert write_review([], tmp_path, NOW) is None
    assert list(tmp_path.iterdir()) == []


def test_text_that_could_run_as_a_formula_is_quoted_in_the_review_file(tmp_path):
    path = write_review([placed_item("=HYPERLINK(1)")], tmp_path, NOW)

    assert path is not None
    [row] = list(csv.DictReader(path.open()))
    assert row["log_name"] == "'=HYPERLINK(1)"
    assert row["new_lng"] == "-72.248"


@pytest.mark.parametrize("start", ["=", "+", "-", "@"])
def test_cell_quotes_formula_starts_in_text_only(start):
    assert cell(f"{start}1+1") == f"'{start}1+1"
    assert cell("Main St") == "Main St"
    assert cell(-72.25) == -72.25


# --- the AI choice ---


class Recorder:
    def __init__(self) -> None:
        self.calls = []

    def record(self, call):
        self.calls.append(call)
        return "id"


def candidates() -> list[Candidate]:
    return place_candidates_for_quarry()


def place_candidates_for_quarry() -> list[Candidate]:
    from locations.osm import place_candidates

    return place_candidates(SNAPSHOT, "QUARRY HILL TOWN HOUSES", "MOUNT SUPPORT RD")


def test_the_prompt_lists_numbered_candidates_and_says_to_answer_none_when_unsure():
    prompt = place_match_prompt("Quarry Hill", "MOUNT SUPPORT RD", candidates())

    assert '"n": 1' in prompt and '"n": 2' in prompt
    assert "Quarry Hill Town Houses" in prompt
    assert "Answer 0 unless you are sure" in prompt
    assert "not instructions" in prompt
    assert "coordinates" not in prompt.split("Rules:")[0].lower()


def test_a_chosen_number_gives_that_candidate_and_the_call_is_recorded():
    backend = FakeBackend([{"choice": 2, "reason": "same name"}])
    recorder = Recorder()

    chosen = pick_candidate(
        backend, recorder, "Quarry", "MOUNT SUPPORT RD", candidates()
    )

    assert chosen is not None and chosen.feature.ref == "node/12"
    [call] = recorder.calls
    assert (call.field, call.outcome, call.prompt_version) == (
        "place_match",
        "ok",
        "place_match-1",
    )
    assert call.accepted == [{"name": "Quarry Hill Marketing", "ref": "node/12"}]


def test_zero_means_none():
    backend = FakeBackend([{"choice": 0, "reason": "not sure"}])

    assert pick_candidate(backend, Recorder(), "Quarry", "S", candidates()) is None


@pytest.mark.parametrize("choice", [3, -1, 99])
def test_a_number_out_of_range_is_a_failed_call_not_a_match(choice):
    backend = FakeBackend([{"choice": choice, "reason": "x"}])
    recorder = Recorder()

    with pytest.raises(AiCallFailed, match="outside 0 to 2"):
        pick_candidate(backend, recorder, "Quarry", "S", candidates())
    assert recorder.calls[0].outcome == "failed"


def test_an_answer_off_schema_is_a_failed_call():
    backend = FakeBackend([{"pick": "first"}])

    with pytest.raises(AiCallFailed, match="off schema"):
        pick_candidate(backend, Recorder(), "Quarry", "S", candidates())


def test_an_unavailable_backend_is_recorded_and_raised():
    backend = FakeBackend([AiBackendUnavailable("logged out")])
    recorder = Recorder()

    with pytest.raises(AiBackendUnavailable):
        pick_candidate(backend, recorder, "Quarry", "S", candidates())
    assert recorder.calls[0].outcome == "unavailable"


# --- the command ---


@pytest.fixture
def snapshot_dir(tmp_path, monkeypatch):
    directory = tmp_path / "osm"
    directory.mkdir()
    (directory / "snapshot-2026-11-20.json").write_text(SNAPSHOT.to_json())
    monkeypatch.setattr(geocode_job, "DEFAULT_SNAPSHOT_DIR", directory)
    monkeypatch.setattr(geocode_job, "REVIEW_DIR", tmp_path / "review")
    return directory


def test_main_retries_prints_the_summary_and_writes_the_review_file(
    db_session, snapshot_dir, tmp_path, capsys
):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
        **approximate(),
    )

    status = geocode_job.main(["--retry-approximate", "--no-llm"])

    out = capsys.readouterr().out
    assert status == 0
    assert "Retry: 1 rows placed" in out
    assert "1 placed (1 by address)" in out
    assert "Review the placements in" in out
    assert len(list((tmp_path / "review").glob("geocode-matches-*.csv"))) == 1


def test_main_retry_without_a_snapshot_fails_and_says_why(
    db_session, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(geocode_job, "DEFAULT_SNAPSHOT_DIR", tmp_path / "none")

    status = geocode_job.main(["--retry-approximate"])

    assert status == 1
    assert "osm-snapshot" in capsys.readouterr().err


def test_main_goes_on_without_ai_and_says_so(db_session, snapshot_dir, capsys):
    place_row(db_session)

    def logged_out():
        raise AiBackendUnavailable("not logged in")

    geocode_job.main([], geocoder=NoNominatim(), backend_factory=logged_out)

    captured = capsys.readouterr()
    assert "No AI for place names" in captured.err


# --- research pins are exact, and nothing overwrites them ---


def researched(**columns) -> dict:
    return {
        "lat": 43.6700,
        "lng": -72.2600,
        "coordinate_precision": "exact",
        "geocoded_via": "research",
        "geocode_source_url": "https://example.com/page",
        **columns,
    }


def test_the_retry_skips_a_research_pin(db_session):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
        **researched(),
    )

    counts = geocode_job.run_retry(OsmLocator(SNAPSHOT))

    row = the_row(db_session, "8 COMMERCE AVE")
    assert (row.lat, row.geocoded_via) == (43.67, "research")
    assert counts.groups_retried == 0


def test_a_run_does_not_look_up_a_row_that_has_a_research_pin(db_session):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
        **researched(),
    )
    geocoder = NoNominatim()

    geocode_job.run(geocoder, locator=OsmLocator(SNAPSHOT))

    assert geocoder.queries == []
    assert the_row(db_session, "8 COMMERCE AVE").geocoded_via == "research"


def test_another_spelling_copies_a_research_pin_with_its_link(db_session):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
        **researched(),
    )
    add_row(
        db_session,
        "8 COMMERCE AV",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
    )

    geocode_job.run(NoNominatim(), locator=OsmLocator(SNAPSHOT))

    copy = the_row(db_session, "8 COMMERCE AV")
    assert (copy.lat, copy.geocoded_via, copy.geocode_source_url) == (
        43.67,
        "research",
        "https://example.com/page",
    )


# --- an approximate answer from Nominatim, and the retry's groups ---


def test_an_approximate_nominatim_answer_is_tried_against_the_snapshot(db_session):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
    )
    geocoder = NoNominatim(
        {"8 COMMERCE AVE, Lebanon, NH": GeocodeResult(43.65, -72.25, "approximate")}
    )

    counts = geocode_job.run(geocoder, locator=OsmLocator(SNAPSHOT))

    row = the_row(db_session, "8 COMMERCE AVE")
    assert (row.geocoded_via, row.coordinate_precision, row.osm_ref) == (
        "osm",
        "exact",
        "way/10",
    )
    assert counts.requests == 1


def test_an_approximate_answer_is_kept_when_the_snapshot_has_nothing(db_session):
    add_row(
        db_session,
        "9 COMMERCE AVE",
        normalized_address="9 Commerce Ave",
        street="COMMERCE AVE",
    )
    geocoder = NoNominatim(
        {"9 COMMERCE AVE, Lebanon, NH": GeocodeResult(43.65, -72.25, "approximate")}
    )

    counts = geocode_job.run(geocoder, locator=OsmLocator(SNAPSHOT))

    row = the_row(db_session, "9 COMMERCE AVE")
    assert (row.lat, row.lng, row.coordinate_precision, row.geocoded_via) == (
        43.65,
        -72.25,
        "approximate",
        "nominatim",
    )
    # The street was not asked for, since the query's own point is the one kept.
    assert geocoder.queries == ["9 COMMERCE AVE, Lebanon, NH"]
    assert counts.requests == 1


def test_the_retry_tries_each_row_of_a_group_until_one_matches(db_session):
    # The first row has no street, so the snapshot cannot place it. The second can.
    place_row(db_session, "QUARRY NO STREET", street=None, **approximate())
    place_row(db_session, "QUARRY WITH STREET", **approximate())
    picks = Picks(0)

    counts = geocode_job.run_retry(OsmLocator(SNAPSHOT, picks))

    assert the_row(db_session, "QUARRY NO STREET").osm_ref == "node/11"
    assert the_row(db_session, "QUARRY WITH STREET").osm_ref == "node/11"
    assert (counts.placed, counts.groups_kept) == (2, 0)


def test_spellings_that_would_be_looked_up_alike_are_tried_once(db_session):
    place_row(db_session, "QUARRY HILL TH", **approximate())
    place_row(db_session, "QUARRY HILL TOWNHOUSES", **approximate())
    picks = Picks(None)

    counts = geocode_job.run_retry(OsmLocator(SNAPSHOT, picks))

    assert len(picks.calls) == 1
    assert counts.groups_kept == 1


@pytest.mark.parametrize("kind", ["highway"])
def test_the_retry_leaves_out_kinds_the_snapshot_cannot_place(db_session, kind):
    add_row(
        db_session,
        "I-89 NB",
        kind=kind,
        normalized_address="I-89 northbound near exit 18",
        **approximate(),
    )

    assert geocode_job.run_retry(OsmLocator(SNAPSHOT)).groups_retried == 0


def test_a_run_goes_on_without_ai_when_mongodb_is_not_available(
    db_session, snapshot_dir, monkeypatch, capsys
):
    def no_mongo():
        raise RuntimeError("no mongo settings")

    monkeypatch.setattr(geocode_job, "get_db", no_mongo)
    args = geocode_job._parse_args([])

    locator = geocode_job._make_locator(args, snapshot_dir, lambda: FakeBackend())

    assert locator is not None and locator.picker is None
    err = capsys.readouterr().err
    assert "MongoDB is not available" in err
    assert "RuntimeError: no mongo settings" in err


@pytest.mark.parametrize("text", ["=A1", "+1", "-1", "@SUM", "\tx", "\rx"])
def test_every_quoted_start_survives_a_round_trip(text):
    assert cell(text) == "'" + text
    assert uncell(cell(text)) == text


def test_text_that_merely_starts_with_a_quote_is_left_alone():
    assert uncell("'Quarry") == "'Quarry"
    assert uncell("Quarry") == "Quarry"


def test_another_spelling_copies_an_osm_pin_with_its_reference(db_session):
    add_row(
        db_session,
        "8 COMMERCE AVE",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
        lat=43.6501,
        lng=-72.248,
        coordinate_precision="exact",
        geocoded_via="osm",
        osm_ref="way/10",
    )
    add_row(
        db_session,
        "8 COMMERCE AV",
        normalized_address="8 Commerce Ave",
        street="COMMERCE AVE",
    )

    geocode_job.run(NoNominatim(), locator=OsmLocator(SNAPSHOT))

    copy = the_row(db_session, "8 COMMERCE AV")
    assert (copy.geocoded_via, copy.osm_ref) == ("osm", "way/10")
