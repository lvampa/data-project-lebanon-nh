from mongo.init import init_indexes


def index_keys(collection) -> dict[str, tuple]:
    return {
        name: (tuple(info["key"]), info.get("unique", False))
        for name, info in collection.index_information().items()
    }


def test_the_archive_gets_its_three_indexes(raw_sources):
    init_indexes()

    indexes = index_keys(raw_sources)
    assert indexes["source_1_source_key_1_content_hash_1"] == (
        (("source", 1), ("source_key", 1), ("content_hash", 1)),
        True,
    )
    assert indexes["source_1_source_key_1_first_fetched_at_-1"][0] == (
        ("source", 1),
        ("source_key", 1),
        ("first_fetched_at", -1),
    )
    assert indexes["source_1_last_seen_at_1"][0] == (
        ("source", 1),
        ("last_seen_at", 1),
    )
    raw_sources.database["urls"].drop()
    raw_sources.database["ai_calls"].drop()


def test_the_ai_call_log_gets_its_two_indexes(raw_sources, ai_calls):
    init_indexes()

    indexes = index_keys(ai_calls)
    assert indexes["field_1_prompt_version_1_called_at_-1"][0] == (
        ("field", 1),
        ("prompt_version", 1),
        ("called_at", -1),
    )
    assert indexes["accepted.raw_1"][0] == (("accepted.raw", 1),)
    raw_sources.database["urls"].drop()


def test_running_it_twice_is_harmless(raw_sources):
    init_indexes()
    init_indexes()

    assert len(raw_sources.index_information()) == 4
    raw_sources.database["urls"].drop()
    raw_sources.database["ai_calls"].drop()
