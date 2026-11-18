from bootstrap_testing.names import MAX_NAME_LENGTH, checkout_database_name


def test_a_name_comes_from_the_checkout_folder():
    assert checkout_database_name("app", "My Worktree-2") == "app_my_worktree_2_test"
    assert checkout_database_name("scraped_data", "main") == "scraped_data_main_test"


def test_a_long_folder_name_is_cut_to_the_identifier_limit_and_stays_distinct():
    first = checkout_database_name("scraped_data", "a" * 80 + "-one")
    second = checkout_database_name("scraped_data", "a" * 80 + "-two")

    assert len(first) == len(second) == MAX_NAME_LENGTH
    assert first != second
    assert first.endswith("_test")


def test_the_default_name_ends_in_test_and_is_a_valid_identifier():
    name = checkout_database_name("app")

    assert name.startswith("app_")
    assert name.endswith("_test")
    assert name.replace("_", "").isalnum()
    assert name == name.lower()
