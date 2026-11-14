"""The normalization job, against the real test databases and a scripted backend."""

import json
from datetime import date, datetime

import pytest
from mongo.ai_calls import AiCallLog
from postgres.models.address_normalization import AddressNormalization
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from postgres.models.property import Property
from sqlalchemy import select

from scripts.normalize import job
from scripts.normalize.backends import (
    AiBackendUnavailable,
    AiCallFailed,
    FakeBackend,
)
from scripts.normalize.prompts import (
    INCIDENT_TYPE_PROMPT_VERSION,
    location_prompt_version,
)
from scripts.normalize.rules import rules_prompt_version

NOW = datetime(2026, 11, 13)


# --- data helpers ---


def add_entry(session, case_number: str, **columns) -> None:
    session.add(
        LogEntry(
            case_number=case_number,
            source_url="https://example.com/log.pdf",
            log_date=date(2026, 5, 11),
            created_at=NOW,
            updated_at=NOW,
            **columns,
        )
    )
    session.commit()


def add_types(session, *raw_values: str) -> None:
    for number, raw in enumerate(raw_values):
        add_entry(session, f"t-{raw}-{number}", incident_type=raw)


def add_locations(session, *raw_values: str, place_code: str | None = None) -> None:
    for number, raw in enumerate(raw_values):
        add_entry(session, f"l-{raw}-{number}", location=raw, place_code=place_code)


def add_parcels(session, *locations: str) -> None:
    for location in locations:
        session.add(
            Property(
                parcel_id=f"p-{location}",
                location=location,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    session.commit()


def type_row(session, raw: str) -> IncidentTypeCategory | None:
    session.expire_all()
    return session.scalar(
        select(IncidentTypeCategory).where(
            IncidentTypeCategory.raw_incident_type == raw
        )
    )


def address_row(session, raw: str) -> AddressNormalization | None:
    session.expire_all()
    return session.scalar(
        select(AddressNormalization).where(AddressNormalization.raw_address == raw)
    )


def the_type(session, raw: str) -> IncidentTypeCategory:
    row = type_row(session, raw)
    assert row is not None, raw
    return row


def the_address(session, raw: str) -> AddressNormalization:
    row = address_row(session, raw)
    assert row is not None, raw
    return row


def add_type_row(session, raw: str, **columns) -> None:
    session.add(
        IncidentTypeCategory(
            raw_incident_type=raw, created_at=NOW, updated_at=NOW, **columns
        )
    )
    session.commit()


def add_address_row(session, raw: str, **columns) -> None:
    session.add(
        AddressNormalization(raw_address=raw, created_at=NOW, updated_at=NOW, **columns)
    )
    session.commit()


# --- scripted answers ---


def type_item(raw: str, **overrides: object) -> dict[str, object]:
    return {
        "raw": raw,
        "category": "Traffic",
        "normalized_type": "Motor vehicle complaint",
        "unsure": False,
        **overrides,
    }


def type_answer(*raws: str, **overrides: object) -> dict[str, object]:
    return {"items": [type_item(raw, **overrides) for raw in raws]}


def location_item(raw: str, **overrides: object) -> dict[str, object]:
    return {
        "raw": raw,
        "kind": "place",
        "normalized_address": "Hannaford, Market St",
        "geocode_query": "Hannaford, Market St, Lebanon, NH",
        "street": "MARKET ST",
        "unsure": False,
        **overrides,
    }


def location_answer(*raws: str, **overrides: object) -> dict[str, object]:
    return {"items": [location_item(raw, **overrides) for raw in raws]}


@pytest.fixture
def call_log(ai_calls) -> AiCallLog:
    return AiCallLog(ai_calls)


def run(backend, call_log, *, fields=("incident_type", "location"), redo=False, **kw):
    return job.run(backend, call_log, fields=fields, redo=redo, **kw)


def sent_values(backend: FakeBackend, call: int = 0) -> list[str]:
    """The raw values the prompt of one call carried, read from its JSON list."""
    prompt = backend.calls[call].prompt
    return json.loads(prompt.rsplit("Raw values (JSON): ", 1)[1].strip())


# =====================================================================
# incident types
# =====================================================================


def test_a_waiting_incident_type_is_stored_with_its_source_version_and_call(
    db_session, call_log
):
    add_types(db_session, "MV COMPLAINT")
    backend = FakeBackend(replies=[type_answer("MV COMPLAINT")])

    result = run(backend, call_log, fields=("incident_type",))

    row = the_type(db_session, "MV COMPLAINT")
    assert (row.category, row.normalized_type) == ("Traffic", "Motor vehicle complaint")
    assert (row.source, row.prompt_version) == ("ai", INCIDENT_TYPE_PROMPT_VERSION)
    assert row.needs_review is False
    [call] = call_log.calls("incident_type", INCIDENT_TYPE_PROMPT_VERSION)
    assert row.ai_call_id == str(call["_id"])
    assert (call["ai_backend"], call["outcome"]) == ("fake", "ok")
    assert result.calls == 1


def test_values_that_differ_only_in_case_or_spacing_are_sent_once(db_session, call_log):
    add_types(db_session, "Noise", "NOISE", "noise  ")
    backend = FakeBackend(replies=[type_answer("NOISE")])

    run(backend, call_log, fields=("incident_type",))

    # One of the three is sent: the first in sorted order.
    assert sent_values(backend) == ["NOISE"]
    for raw in ("Noise", "NOISE", "noise  "):
        assert the_type(db_session, raw).category == "Traffic"


def test_a_value_with_a_stored_normalization_is_never_sent_again(db_session, call_log):
    add_types(db_session, "MV COMPLAINT")
    first = FakeBackend(replies=[type_answer("MV COMPLAINT")])
    run(first, call_log, fields=("incident_type",))
    second = FakeBackend(replies=[])

    result = run(second, call_log, fields=("incident_type",))

    assert second.calls == []
    assert result.calls == 0


def test_a_new_spelling_copies_the_stored_value_and_source_with_no_call(
    db_session, call_log
):
    add_types(db_session, "Noise")
    add_type_row(
        db_session,
        "NOISE",
        category="Police",
        normalized_type="Noise complaint",
        source="human",
    )
    backend = FakeBackend(replies=[])

    run(backend, call_log, fields=("incident_type",))

    copy = the_type(db_session, "Noise")
    assert (copy.category, copy.normalized_type, copy.source) == (
        "Police",
        "Noise complaint",
        "human",
    )
    assert backend.calls == []


def test_a_human_row_is_never_overwritten(db_session, call_log):
    add_types(db_session, "NOISE")
    add_type_row(db_session, "NOISE", category="Police", source="human")
    backend = FakeBackend(replies=[])

    run(backend, call_log, fields=("incident_type",))
    run(backend, call_log, fields=("incident_type",), redo=True)

    assert backend.calls == []
    row = the_type(db_session, "NOISE")
    assert (row.category, row.source) == ("Police", "human")


def test_the_names_already_in_use_go_in_the_prompt(db_session, call_log):
    add_types(db_session, "NOISE", "ALARM")
    add_type_row(
        db_session,
        "NOISE",
        category="Police",
        normalized_type="Noise complaint",
        source="ai",
        prompt_version=INCIDENT_TYPE_PROMPT_VERSION,
    )
    backend = FakeBackend(replies=[type_answer("ALARM")])

    run(backend, call_log, fields=("incident_type",))

    assert json.dumps(["Noise complaint"]) in backend.calls[0].prompt


def test_a_name_that_differs_from_one_in_use_only_in_case_is_snapped(
    db_session, call_log
):
    add_types(db_session, "NOISE", "ALARM")
    add_type_row(
        db_session,
        "NOISE",
        category="Police",
        normalized_type="Noise complaint",
        source="ai",
        prompt_version=INCIDENT_TYPE_PROMPT_VERSION,
    )
    backend = FakeBackend(
        replies=[type_answer("ALARM", normalized_type="noise  COMPLAINT")]
    )

    run(backend, call_log, fields=("incident_type",))

    assert the_type(db_session, "ALARM").normalized_type == "Noise complaint"


def test_an_unsure_answer_is_stored_with_a_review_mark(db_session, call_log):
    add_types(db_session, "MV COMPLAINT")
    backend = FakeBackend(replies=[type_answer("MV COMPLAINT", unsure=True)])

    run(backend, call_log, fields=("incident_type",))

    assert the_type(db_session, "MV COMPLAINT").needs_review is True


@pytest.mark.parametrize(
    "override",
    [{"category": "Parking"}, {"normalized_type": "MV complaint"}],
    ids=["category_outside_the_five", "abbreviation_in_the_name"],
)
def test_a_discarded_item_stores_no_value_and_costs_an_attempt(
    db_session, call_log, override
):
    add_types(db_session, "MV COMPLAINT")
    backend = FakeBackend(replies=[type_answer("MV COMPLAINT", **override)])

    result = run(backend, call_log, fields=("incident_type",))

    row = the_type(db_session, "MV COMPLAINT")
    assert (row.category, row.source, row.failed_attempts) == (None, None, 1)
    assert result.summary("incident_type").discarded == 1
    assert result.summary("incident_type").waiting == 1


def test_a_value_the_answer_leaves_out_costs_an_attempt_and_stays_waiting(
    db_session, call_log
):
    add_types(db_session, "A", "B")
    backend = FakeBackend(replies=[type_answer("A")])

    run(backend, call_log, fields=("incident_type",))

    assert the_type(db_session, "A").category == "Traffic"
    missing = the_type(db_session, "B")
    assert (missing.category, missing.failed_attempts) == (None, 1)


def test_a_value_that_failed_three_times_is_marked_and_not_sent_again(
    db_session, call_log
):
    add_types(db_session, "A")
    for _ in range(3):
        run(
            FakeBackend(replies=[type_answer("OTHER")]),
            call_log,
            fields=("incident_type",),
        )
    again = FakeBackend(replies=[])

    run(again, call_log, fields=("incident_type",))

    row = the_type(db_session, "A")
    assert (row.failed_attempts, row.needs_review, row.category) == (3, True, None)
    assert again.calls == []


def test_an_item_for_a_value_never_sent_costs_nothing_and_creates_no_row(
    db_session, call_log
):
    add_types(db_session, "A")
    backend = FakeBackend(replies=[type_answer("A", "INVENTED")])

    run(backend, call_log, fields=("incident_type",))

    assert type_row(db_session, "INVENTED") is None


def test_a_failed_call_stores_nothing_charges_nothing_and_the_run_goes_on(
    db_session, call_log
):
    add_types(db_session, "A")
    backend = FakeBackend(replies=[AiCallFailed("timed out")])

    result = run(backend, call_log, fields=("incident_type",))

    assert type_row(db_session, "A") is None
    assert (result.calls, result.failed_calls) == (1, 1)
    assert result.summary("incident_type").waiting == 1
    [call] = call_log.calls("incident_type", INCIDENT_TYPE_PROMPT_VERSION)
    assert call["outcome"] == "failed"
    assert "timed out" in call["error"]


@pytest.mark.parametrize(
    "reply",
    [{}, {"items": "no"}, {"other": 1}],
    ids=["empty", "not_a_list", "wrong_shape"],
)
def test_an_empty_or_off_schema_answer_stores_nothing_and_charges_nothing(
    db_session, call_log, reply
):
    add_types(db_session, "A")
    backend = FakeBackend(replies=[reply])

    result = run(backend, call_log, fields=("incident_type",))

    assert type_row(db_session, "A") is None
    assert result.failed_calls == 1


def test_a_backend_that_is_logged_out_stops_every_later_call(db_session, call_log):
    add_types(db_session, "A")
    add_locations(db_session, "SOMEWHERE")
    add_parcels(db_session, "1 Main St")
    backend = FakeBackend(replies=[AiBackendUnavailable("Not logged in")])

    result = run(backend, call_log)

    assert len(backend.calls) == 1
    assert (result.stopped, result.failed_calls) == (True, 1)
    assert result.every_call_failed


# --- redo ---


def test_redo_sends_ai_rows_on_an_older_prompt_and_nothing_else(db_session, call_log):
    add_types(db_session, "OLD", "CURRENT", "HUMAN")
    add_type_row(
        db_session,
        "OLD",
        category="Police",
        normalized_type="Old",
        source="ai",
        prompt_version="incident_type-0",
    )
    add_type_row(
        db_session,
        "CURRENT",
        category="Fire",
        normalized_type="Current",
        source="ai",
        prompt_version=INCIDENT_TYPE_PROMPT_VERSION,
    )
    add_type_row(
        db_session, "HUMAN", category="EMS", normalized_type="Mine", source="human"
    )
    backend = FakeBackend(replies=[type_answer("OLD")])

    run(backend, call_log, fields=("incident_type",), redo=True)

    assert sent_values(backend) == ["OLD"]
    row = the_type(db_session, "OLD")
    assert (row.category, row.prompt_version) == (
        "Traffic",
        INCIDENT_TYPE_PROMPT_VERSION,
    )


def test_a_second_redo_sends_nothing(db_session, call_log):
    add_types(db_session, "OLD")
    add_type_row(
        db_session,
        "OLD",
        category="Police",
        normalized_type="Old",
        source="ai",
        prompt_version="incident_type-0",
    )
    run(
        FakeBackend(replies=[type_answer("OLD")]),
        call_log,
        fields=("incident_type",),
        redo=True,
    )
    second = FakeBackend(replies=[])

    run(second, call_log, fields=("incident_type",), redo=True)

    assert second.calls == []


def test_redo_keeps_the_old_value_until_a_valid_new_one_arrives(db_session, call_log):
    add_types(db_session, "OLD")
    add_type_row(
        db_session,
        "OLD",
        category="Police",
        normalized_type="Old",
        source="ai",
        prompt_version="incident_type-0",
    )
    backend = FakeBackend(replies=[type_answer("OLD", category="Parking")])

    run(backend, call_log, fields=("incident_type",), redo=True)

    row = the_type(db_session, "OLD")
    assert (row.category, row.normalized_type, row.prompt_version) == (
        "Police",
        "Old",
        "incident_type-0",
    )


# --- batches and the call budget ---


def test_values_go_in_batches_of_fifty(db_session, call_log):
    raws = [f"TYPE {n:03d}" for n in range(120)]
    add_types(db_session, *raws)
    backend = FakeBackend(
        replies=[
            type_answer(*raws[0:50]),
            type_answer(*raws[50:100]),
            type_answer(*raws[100:120]),
        ]
    )

    result = run(backend, call_log, fields=("incident_type",))

    assert [len(sent_values(backend, n)) for n in range(3)] == [50, 50, 20]
    assert result.calls == 3


@pytest.mark.parametrize(
    ("needed", "allowed"),
    [
        ({"incident_type": 6, "location": 5}, {"incident_type": 5, "location": 5}),
        ({"incident_type": 6, "location": 1}, {"incident_type": 6, "location": 1}),
        ({"incident_type": 12, "location": 0}, {"incident_type": 10, "location": 0}),
        ({"incident_type": 0, "location": 12}, {"incident_type": 0, "location": 10}),
        ({"incident_type": 3, "location": 3}, {"incident_type": 3, "location": 3}),
        ({"incident_type": 20, "location": 20}, {"incident_type": 5, "location": 5}),
    ],
)
def test_each_field_gets_five_calls_and_unused_ones_pass_to_the_other(needed, allowed):
    assert job.allocate_calls(needed) == allowed


def test_calls_a_field_does_not_use_pass_to_the_other(db_session, call_log):
    raws = [f"TYPE {n:03d}" for n in range(600)]
    add_types(db_session, *raws)
    backend = FakeBackend(
        replies=[type_answer(*raws[n * 50 : n * 50 + 50]) for n in range(10)]
    )

    result = run(backend, call_log)

    assert result.calls == 10
    assert result.summary("incident_type").waiting == 100


# --- the call record ---


def test_a_call_that_stored_everything_is_recorded_ok_and_a_partial_one_partial(
    db_session, call_log
):
    add_types(db_session, "A", "B")
    backend = FakeBackend(replies=[type_answer("A")])

    run(backend, call_log, fields=("incident_type",))

    [call] = call_log.calls("incident_type", INCIDENT_TYPE_PROMPT_VERSION)
    assert call["outcome"] == "partial"
    assert [item["raw"] for item in call["accepted"]] == ["A"]
    assert call["raw_values"] == ["A", "B"]
    assert json.loads(call["raw_answer"])["items"][0]["raw"] == "A"


def test_with_mongodb_unreachable_the_values_are_stored_and_lost_records_counted(
    db_session, monkeypatch
):
    from mongo.ai_calls import ai_calls_collection
    from mongo.client import MongoDB

    monkeypatch.setenv("MONGO_HOST", "127.0.0.1")
    monkeypatch.setenv("MONGO_PORT", "1")
    add_types(db_session, "A")
    backend = FakeBackend(replies=[type_answer("A")])

    result = run(
        backend, AiCallLog(ai_calls_collection(MongoDB())), fields=("incident_type",)
    )

    row = the_type(db_session, "A")
    assert (row.category, row.source, row.ai_call_id) == ("Traffic", "ai", None)
    assert result.records_lost == 1


# =====================================================================
# locations
# =====================================================================


def test_an_address_on_a_listed_street_is_settled_by_a_rule_and_never_sent(
    db_session, call_log
):
    add_parcels(db_session, "7 Main St", "9 Elm St")
    add_locations(db_session, "12 MAIN STREET")
    backend = FakeBackend(replies=[])

    result = run(backend, call_log, fields=("location",))

    row = the_address(db_session, "12 MAIN STREET")
    assert (row.kind, row.source, row.prompt_version) == (
        "address",
        "rule",
        rules_prompt_version(),
    )
    assert row.normalized_address == "12 Main St"
    assert row.geocode_query == "12 Main St, Lebanon, NH"
    assert backend.calls == []
    assert result.summary("location").waiting == 0


def test_a_leftover_goes_to_the_ai_with_the_street_list_in_the_prompt(
    db_session, call_log
):
    add_parcels(db_session, "7 Main St", "9 Market St")
    add_locations(db_session, "HANNAFORDS - MARKET ST")
    backend = FakeBackend(replies=[location_answer("HANNAFORDS - MARKET ST")])

    run(backend, call_log, fields=("location",))

    assert json.dumps(["MAIN ST", "MARKET ST"]) in backend.calls[0].prompt
    assert sent_values(backend) == ["HANNAFORDS - MARKET ST"]
    row = the_address(db_session, "HANNAFORDS - MARKET ST")
    assert (row.kind, row.source, row.street) == ("place", "ai", "MARKET ST")
    assert row.normalized_address == "Hannaford, Market St"
    assert row.geocode_query == "Hannaford, Market St, Lebanon, NH"
    assert row.prompt_version == location_prompt_version(["MAIN ST", "MARKET ST"])
    assert row.needs_review is False


def test_the_ai_is_sent_the_raw_value_not_the_canonical_form(db_session, call_log):
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "Hannaford's Market - Market Street")
    backend = FakeBackend(
        replies=[location_answer("Hannaford's Market - Market Street")]
    )

    run(backend, call_log, fields=("location",))

    assert sent_values(backend) == ["Hannaford's Market - Market Street"]


def test_a_street_the_ai_names_that_is_not_listed_gets_a_review_mark(
    db_session, call_log
):
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "RT 4")
    backend = FakeBackend(
        replies=[location_answer("RT 4", kind="highway", street="Route 4")]
    )

    run(backend, call_log, fields=("location",))

    assert the_address(db_session, "RT 4").needs_review is True


def test_spellings_with_the_same_canonical_form_are_sent_once(db_session, call_log):
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "SOMEWHERE ROAD", "Somewhere Rd", "somewhere  road")
    backend = FakeBackend(replies=[location_answer("SOMEWHERE ROAD")])

    run(backend, call_log, fields=("location",))

    assert sent_values(backend) == ["SOMEWHERE ROAD"]
    for raw in ("SOMEWHERE ROAD", "Somewhere Rd", "somewhere  road"):
        assert the_address(db_session, raw).source == "ai"


def test_with_no_street_list_there_are_no_location_ai_calls(db_session, call_log):
    add_locations(db_session, "SOMEWHERE")
    backend = FakeBackend(replies=[])

    result = run(backend, call_log, fields=("location",))

    assert backend.calls == []
    assert result.summary("location").waiting == 1
    assert result.street_list_was_empty


def test_with_no_street_list_a_known_place_code_still_settles_a_location(
    db_session, call_log
):
    add_address_row(
        db_session,
        "HANNAFORDS - MARKET ST",
        normalized_address="Hannaford, Market St",
        kind="place",
        place_code="L HANNAF",
        source="ai",
        prompt_version="location-1+streets-aaaaaaaa",
    )
    add_locations(
        db_session, "HANNAFORDS MARKET - MARKET STREET", place_code="L HANNAF"
    )
    backend = FakeBackend(replies=[])

    run(backend, call_log, fields=("location",))

    row = the_address(db_session, "HANNAFORDS MARKET - MARKET STREET")
    assert (row.kind, row.source, row.normalized_address) == (
        "place",
        "rule",
        "Hannaford, Market St",
    )
    assert backend.calls == []


def test_a_place_code_with_a_review_mark_is_not_reused(db_session, call_log):
    add_parcels(db_session, "7 Main St")
    add_address_row(
        db_session,
        "HANNAFORDS - MARKET ST",
        normalized_address="Hannaford, Market St",
        kind="place",
        place_code="L HANNAF",
        source="ai",
        needs_review=True,
    )
    add_locations(
        db_session, "HANNAFORDS MARKET - MARKET STREET", place_code="L HANNAF"
    )
    backend = FakeBackend(
        replies=[location_answer("HANNAFORDS MARKET - MARKET STREET")]
    )

    run(backend, call_log, fields=("location",))

    assert len(backend.calls) == 1


def test_a_human_location_is_never_touched(db_session, call_log):
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "12 MAIN ST")
    add_address_row(
        db_session,
        "12 MAIN ST",
        normalized_address="Mine",
        kind="address",
        source="human",
    )
    backend = FakeBackend(replies=[])

    run(backend, call_log, fields=("location",))
    run(backend, call_log, fields=("location",), redo=True)

    row = the_address(db_session, "12 MAIN ST")
    assert (row.normalized_address, row.source) == ("Mine", "human")


def test_a_second_run_sends_no_location_again(db_session, call_log):
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "SOMEWHERE")
    run(
        FakeBackend(replies=[location_answer("SOMEWHERE")]),
        call_log,
        fields=("location",),
    )
    second = FakeBackend(replies=[])

    run(second, call_log, fields=("location",))

    assert second.calls == []


def test_redo_skips_rows_already_on_the_current_street_list_version(
    db_session, call_log
):
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "SOMEWHERE")
    run(
        FakeBackend(replies=[location_answer("SOMEWHERE")]),
        call_log,
        fields=("location",),
    )
    second = FakeBackend(replies=[])

    run(second, call_log, fields=("location",), redo=True)

    assert second.calls == []


def test_a_new_street_changes_the_version_so_redo_asks_again(db_session, call_log):
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "SOMEWHERE")
    run(
        FakeBackend(replies=[location_answer("SOMEWHERE")]),
        call_log,
        fields=("location",),
    )
    add_parcels(db_session, "1 Oak St")  # a new street changes the list's hash
    again = FakeBackend(
        replies=[location_answer("SOMEWHERE", normalized_address="Somewhere Rd")]
    )

    run(again, call_log, fields=("location",), redo=True)

    assert the_address(db_session, "SOMEWHERE").normalized_address == "Somewhere Rd"


def test_rule_rows_use_the_display_helper_for_their_address(
    db_session, call_log, monkeypatch
):
    monkeypatch.setattr(
        "scripts.normalize.rules.display_form", lambda text: text.title()
    )
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "12 MAIN ST")

    run(FakeBackend(replies=[]), call_log, fields=("location",))

    assert the_address(db_session, "12 MAIN ST").normalized_address == "12 Main St"


def test_redo_asks_the_ai_again_for_a_place_row_and_does_not_copy_its_own_old_value(
    db_session, call_log
):
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "HANNAFORDS PLAZA", place_code="L HANNAF")
    add_address_row(
        db_session,
        "HANNAFORDS PLAZA",
        normalized_address="Hannaford, Market St",
        kind="place",
        place_code="L HANNAF",
        source="ai",
        prompt_version="location-0+streets-old",
    )
    backend = FakeBackend(
        replies=[
            location_answer("HANNAFORDS PLAZA", normalized_address="Hannaford Plaza")
        ]
    )

    run(backend, call_log, fields=("location",), redo=True)

    row = the_address(db_session, "HANNAFORDS PLAZA")
    assert len(backend.calls) == 1
    assert (row.normalized_address, row.source) == ("Hannaford Plaza", "ai")
    assert row.ai_call_id is not None


def test_an_address_that_changes_clears_its_coordinates_so_it_is_placed_again(
    db_session, call_log
):
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "HANNAFORDS PLAZA")
    add_address_row(
        db_session,
        "HANNAFORDS PLAZA",
        normalized_address="Market St",
        kind="highway",
        source="ai",
        prompt_version="location-0+streets-old",
        lat=43.65,
        lng=-72.26,
        geocoded_via="nominatim",
        coordinate_precision="approximate",
        geocode_attempts=2,
    )
    backend = FakeBackend(
        replies=[
            location_answer("HANNAFORDS PLAZA", normalized_address="Hannaford Plaza")
        ]
    )

    run(backend, call_log, fields=("location",), redo=True)

    row = the_address(db_session, "HANNAFORDS PLAZA")
    assert row.normalized_address == "Hannaford Plaza"
    assert (row.lat, row.lng, row.geocoded_via, row.coordinate_precision) == (
        None,
        None,
        None,
        None,
    )
    assert row.geocode_attempts == 0


def test_an_address_that_stays_the_same_keeps_its_coordinates(db_session, call_log):
    add_parcels(db_session, "7 Main St")
    add_locations(db_session, "HANNAFORDS PLAZA")
    add_address_row(
        db_session,
        "HANNAFORDS PLAZA",
        normalized_address="Hannaford, Market St",
        kind="place",
        source="ai",
        prompt_version="location-0+streets-old",
        lat=43.65,
        lng=-72.26,
        geocoded_via="nominatim",
        coordinate_precision="exact",
    )
    backend = FakeBackend(replies=[location_answer("HANNAFORDS PLAZA")])

    run(backend, call_log, fields=("location",), redo=True)

    row = the_address(db_session, "HANNAFORDS PLAZA")
    assert (row.lat, row.lng, row.geocoded_via) == (43.65, -72.26, "nominatim")


def test_a_redo_miss_on_a_row_that_has_a_value_charges_no_attempt(db_session, call_log):
    add_types(db_session, "OLD", "OTHER")
    add_type_row(
        db_session,
        "OLD",
        category="Police",
        normalized_type="Old",
        source="ai",
        prompt_version="incident_type-0",
    )
    backend = FakeBackend(replies=[type_answer("OTHER")])

    run(backend, call_log, fields=("incident_type",), redo=True)

    row = the_type(db_session, "OLD")
    assert (row.failed_attempts, row.needs_review, row.category) == (0, False, "Police")


def test_a_stored_answer_resets_the_failed_attempts(db_session, call_log):
    add_types(db_session, "A")
    add_type_row(db_session, "A", failed_attempts=2)
    backend = FakeBackend(replies=[type_answer("A")])

    run(backend, call_log, fields=("incident_type",))

    assert the_type(db_session, "A").failed_attempts == 0
