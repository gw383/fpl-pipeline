"""Tests for dashboard/formatting.py."""

import math

import pandas as pd
import pytest

from formatting import (
    DEFAULT_NEWS_BANNER,
    NEWS_BANNER_STYLES,
    build_contributor_strings,
    news_banner_html,
    ordinal,
    per_90,
    star_fill,
    stars_html,
)


class TestPer90:
    def test_prorates_to_90_minutes(self):
        assert per_90(9, 45) == 18

    def test_zero_minutes_is_zero(self):
        assert per_90(9, 0) == 0

    def test_rounding(self):
        assert per_90(1, 3, decimals=2) == 30.0


class TestOrdinal:
    @pytest.mark.parametrize(
        ("n", "suffix"),
        [
            (1, "st"),
            (2, "nd"),
            (3, "rd"),
            (4, "th"),
            (11, "th"),
            (12, "th"),
            (13, "th"),
            (20, "th"),
            (21, "st"),
            (22, "nd"),
            (23, "rd"),
            (111, "th"),
            (112, "th"),
        ],
    )
    def test_suffixes(self, n, suffix):
        assert ordinal(n) == suffix


class TestStars:
    @pytest.mark.parametrize(
        ("rating", "fill"),
        [
            (0, [0, 0, 0, 0, 0]),
            (10, [1, 1, 1, 1, 1]),
            (5.0, [1, 1, 0.5, 0, 0]),
            (4.4, [1, 1, 0, 0, 0]),
            (9.9, [1, 1, 1, 1, 0.5]),
            (12, [1, 1, 1, 1, 1]),
            (-3, [0, 0, 0, 0, 0]),
        ],
    )
    def test_fill(self, rating, fill):
        assert star_fill(rating) == fill

    def test_html_always_has_five_stars(self):
        for rating in [0, 2.8, 5, 7.3, 10]:
            assert stars_html(rating).count("★") == 5


class TestNewsBanner:
    @pytest.mark.parametrize("empty", [None, "", math.nan, pd.NA])
    def test_no_news_renders_nothing(self, empty):
        assert news_banner_html(empty) == ""

    def test_colour_follows_first_matching_percentage(self):
        token, background, _ = NEWS_BANNER_STYLES[0]
        html = news_banner_html(f"{token} chance of playing, later 75%")
        assert background in html

    def test_unmatched_text_uses_default_colour(self):
        assert DEFAULT_NEWS_BANNER[0] in news_banner_html("Ineligible for selection")


class TestContributorStrings:
    def test_groups_by_gameweek_with_counts(self):
        rows = pd.DataFrame(
            {
                "gw_id": [11, 11, 11, 10],
                "player": ["Salah", "Gakpo", "Robertson", "Salah"],
                "goals": [2, 1, 0, 0],
                "assists": [0, 0, 1, 1],
            }
        )
        assert build_contributor_strings(rows) == {
            11: ("Salah (2), Gakpo", "Robertson"),
            10: ("", "Salah"),
        }

    def test_empty(self):
        assert build_contributor_strings(pd.DataFrame(columns=["gw_id", "player", "goals", "assists"])) == {}
