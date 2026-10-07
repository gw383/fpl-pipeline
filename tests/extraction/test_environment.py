"""Tests for extraction/environment.py: the live/dev switch."""

import pytest

from environment import current, database_name


@pytest.mark.parametrize(("value", "expected"), [(None, "live"), ("", "live"), ("live", "live"), (" DEV ", "dev")])
def test_environment_defaults_to_live(value, expected):
    assert current({} if value is None else {"FPL_ENV": value}) == expected


def test_an_unknown_environment_is_an_error_not_a_silent_live():
    with pytest.raises(ValueError, match="staging"):
        current({"FPL_ENV": "staging"})


def test_live_uses_the_configured_database():
    assert database_name({}) == "FPL"
    assert database_name({"FPL_DB_NAME": "fpl"}) == "fpl"
    # The dev database's name is ignored outside dev.
    assert database_name({"FPL_DB_NAME": "fpl", "FPL_DB_NAME_DEV": "scratch"}) == "fpl"


def test_dev_uses_its_own_database():
    assert database_name({"FPL_ENV": "dev"}) == "FPL_dev"
    assert database_name({"FPL_ENV": "dev", "FPL_DB_NAME": "fpl"}) == "fpl_dev"
    assert database_name({"FPL_ENV": "dev", "FPL_DB_NAME": "fpl", "FPL_DB_NAME_DEV": "scratch"}) == "scratch"


def test_dev_never_resolves_to_the_live_database():
    """Pointing FPL_DB_NAME_DEV at the live database would defeat the point."""
    with pytest.raises(ValueError, match="same database"):
        database_name({"FPL_ENV": "dev", "FPL_DB_NAME": "fpl", "FPL_DB_NAME_DEV": "FPL"})
