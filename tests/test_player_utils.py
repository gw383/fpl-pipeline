"""Tests for StreamLit/player_utils.py's pure display-formatting helpers.

These only manipulate values already in hand -- no Streamlit runtime and
no database, so they're plain unit tests.
"""
import math

import pandas as pd

from player_utils import news_banner_html, per_90, recommendation_stars


class TestPer90:
    def test_prorates_to_90_minutes(self):
        # 9 points in 45 minutes -> 18 points per 90.
        assert per_90(9, 45) == 18

    def test_zero_minutes_returns_zero_not_a_division_error(self):
        assert per_90(9, 0) == 0

    def test_rounds_to_requested_decimals(self):
        assert per_90(1, 3, decimals=2) == round(1 * 90 / 3, 2)

    def test_full_90_minutes_is_unchanged(self):
        assert per_90(7, 90) == 7


class TestRecommendationStars:
    def test_zero_is_all_empty_stars(self):
        assert recommendation_stars(0) == "☆☆☆☆☆"

    def test_ten_is_all_full_stars(self):
        assert recommendation_stars(10) == "★★★★★"

    def test_half_star_threshold(self):
        # 5.0 / 2 = 2.5 stars -> 2 full + 1 half (0.5 >= 0.25) + 2 empty.
        assert recommendation_stars(5.0) == "★★⯪☆☆"

    def test_below_half_star_threshold_rounds_down(self):
        # 4.4 / 2 = 2.2 stars -> fractional part 0.2 < 0.25, no half star.
        assert recommendation_stars(4.4) == "★★☆☆☆"

    def test_output_length_is_always_five_symbols(self):
        for star in [0, 1, 2.5, 5, 7.3, 9.9, 10]:
            result = recommendation_stars(star)
            # "⯪" only ever appears once; every other character is a
            # single star glyph, so len() and star count line up.
            assert len(result.replace("⯪", "H")) == 5


class TestNewsBannerHtml:
    def test_missing_news_is_empty_string(self):
        assert news_banner_html(None) == ""
        assert news_banner_html("") == ""
        assert news_banner_html(math.nan) == ""
        assert news_banner_html(pd.NA) == ""

    def test_75_percent_chance_uses_its_configured_colour(self):
        html = news_banner_html("75% chance of playing")
        assert "#e8903a" in html
        assert "75% chance of playing" in html

    def test_unmatched_text_falls_back_to_default_banner(self):
        html = news_banner_html("Ineligible for selection")
        assert "#d9534f" in html

    def test_earlier_token_in_style_list_wins_when_multiple_present(self):
        # NEWS_BANNER_STYLES is checked in order: 25% before 50% before 75%.
        html = news_banner_html("25% chance, later becomes 75%")
        assert "#fff3b0" in html
