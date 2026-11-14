from postgres.lock import police_log_lock


def test_the_lock_is_held_by_one_job_at_a_time(test_engine):
    with (
        police_log_lock(test_engine) as first,
        police_log_lock(test_engine) as second,
    ):
        assert (first, second) == (True, False)


def test_the_lock_is_free_again_after_the_job_ends(test_engine):
    with police_log_lock(test_engine):
        pass

    with police_log_lock(test_engine) as again:
        assert again is True
