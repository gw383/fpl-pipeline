"""Tests for StreamLit/colours.py, the shared fixture-difficulty colour
scale used by both components/fixture_card.py and
components/team_fixtures.py (see CHANGELOG for why these used to be two
different scales).
"""
from colours import DIFFICULTY_COLOURS, difficulty_colour


class TestDifficultyColour:
    def test_every_fpl_difficulty_rating_maps_to_a_colour(self):
        for rating in [1, 2, 3, 4, 5]:
            assert difficulty_colour(rating) == DIFFICULTY_COLOURS[rating]

    def test_easiest_and_hardest_are_different_colours(self):
        assert difficulty_colour(1) != difficulty_colour(5)

    def test_accepts_numeric_looking_strings(self):
        # fixture rows coming back from pandas/SQL Server can hand this
        # a numpy int type rather than a plain Python int -- int(x) in
        # difficulty_colour handles anything int()-coercible the same way.
        assert difficulty_colour("3") == DIFFICULTY_COLOURS[3]

    def test_out_of_range_difficulty_falls_back_to_the_middle_band(self):
        assert difficulty_colour(0) == DIFFICULTY_COLOURS[3]
        assert difficulty_colour(9) == DIFFICULTY_COLOURS[3]
