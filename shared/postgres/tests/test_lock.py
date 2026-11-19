from postgres.lock import (
    GEOCODE,
    NORMALIZE,
    POLICE_LOG_PARSE,
    advisory_lock,
    lock_key,
)


def test_the_same_name_is_held_by_one_job_at_a_time(test_engine):
    with (
        advisory_lock(test_engine, GEOCODE) as first,
        advisory_lock(test_engine, GEOCODE) as second,
    ):
        assert (first, second) == (True, False)


def test_different_names_do_not_block_each_other(test_engine):
    with (
        advisory_lock(test_engine, GEOCODE) as geocode,
        advisory_lock(test_engine, POLICE_LOG_PARSE) as parse,
        advisory_lock(test_engine, NORMALIZE) as normalize,
    ):
        assert (geocode, parse, normalize) == (True, True, True)


def test_the_lock_is_free_again_after_the_job_ends(test_engine):
    with advisory_lock(test_engine, NORMALIZE):
        pass

    with advisory_lock(test_engine, NORMALIZE) as again:
        assert again is True


def test_a_name_always_gives_the_same_key():
    # Fixed values, so a key never changes between processes or releases.
    assert lock_key(POLICE_LOG_PARSE) == -3536062753228370824
    assert lock_key(NORMALIZE) == 8539396430110315946
    assert lock_key(GEOCODE) == 7024480840381206256
