"""Tests for dashboard/theme.py colour helpers."""

import pytest

from theme import (
    DIFFICULTY_COLOURS,
    TEXT_PRIMARY,
    difficulty_colour,
    environment_badge_html,
    readable_text_colour,
    rgba,
)


class TestDifficultyColour:
    @pytest.mark.parametrize("rating", [1, 2, 3, 4, 5, "3"])
    def test_ratings_map_to_their_colour(self, rating):
        assert difficulty_colour(rating) == DIFFICULTY_COLOURS[int(rating)]

    @pytest.mark.parametrize("rating", [0, 9, None, "n/a"])
    def test_invalid_ratings_fall_back_to_middle_band(self, rating):
        assert difficulty_colour(rating) == DIFFICULTY_COLOURS[3]


class TestReadableTextColour:
    def test_dark_background_gets_white_text(self):
        assert readable_text_colour("#132257") == "#ffffff"

    def test_light_background_gets_dark_text(self):
        assert readable_text_colour("#FFFFFF") == TEXT_PRIMARY
        assert readable_text_colour("#FFCD00") == TEXT_PRIMARY

    def test_unparseable_colour_defaults_to_white(self):
        assert readable_text_colour("red") == "#ffffff"


def test_rgba():
    assert rgba("#2a78d6", 0.1) == "rgba(42, 120, 214, 0.1)"


def test_environment_badge_names_the_environment_and_stays_out_of_the_way():
    badge = environment_badge_html("dev")
    assert "dev data" in badge and "position:fixed" in badge
    assert "pointer-events:none" in badge  # never blocks a tap on what's underneath
