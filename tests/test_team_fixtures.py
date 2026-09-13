"""Tests for components/team_fixtures.py's ordinal() helper."""
from components.team_fixtures import ordinal


class TestOrdinal:
    def test_first_second_third(self):
        assert ordinal(1) == "st"
        assert ordinal(2) == "nd"
        assert ordinal(3) == "rd"

    def test_fourth_through_ninth_is_th(self):
        for n in range(4, 10):
            assert ordinal(n) == "th"

    def test_teens_are_all_th_even_eleven_twelve_thirteen(self):
        # The general 1/2/3 -> st/nd/rd rule has a well-known exception
        # for the teens (11th, 12th, 13th, not 11st/12nd/13rd).
        for n in [11, 12, 13, 14, 18, 19]:
            assert ordinal(n) == "th"

    def test_twenty_something_follows_the_last_digit_again(self):
        assert ordinal(21) == "st"
        assert ordinal(22) == "nd"
        assert ordinal(23) == "rd"
        assert ordinal(24) == "th"

    def test_hundred_and_teens_are_still_th(self):
        assert ordinal(111) == "th"
        assert ordinal(112) == "th"
        assert ordinal(113) == "th"

    def test_league_table_position_range(self):
        # This is only ever called with a 1-20 Premier League table
        # position in practice; spot-check the full range renders
        # something sane.
        expected = {
            1: "st", 2: "nd", 3: "rd", 4: "th", 5: "th",
            11: "th", 12: "th", 13: "th", 20: "th",
        }
        for position, suffix in expected.items():
            assert ordinal(position) == suffix
