"""Tests for the team-sheet helpers in dashboard/components/pitch.py."""

import base64
import re

import pandas as pd
import pytest

from components.pitch import _display_name, _format_metric, gameweek_points_html, shirt_svg, team_expected_points


def _svg(img: str) -> str:
    """The SVG inside the shirt's data-URI image."""
    return base64.b64decode(re.search(r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)", img).group(1)).decode()


def _fills(img: str) -> list[str]:
    return [part.split('"')[0] for part in _svg(img).split('fill="')[1:]]


def test_shirt_is_an_image_not_inline_svg():
    # st.html strips inline <svg> (DOMPurify's HTML-only profile); images survive.
    html = shirt_svg("#EF0107", "#FFFFFF")
    assert html.startswith("<img") and "<svg" not in html


def test_outfield_shirt_uses_primary_body_and_secondary_trim():
    assert _fills(shirt_svg("#EF0107", "#FFFFFF")) == ["#EF0107", "#FFFFFF", "#FFFFFF"]


def test_goalkeeper_shirt_swaps_the_colours():
    assert _fills(shirt_svg("#EF0107", "#FFFFFF", goalkeeper=True)) == ["#FFFFFF", "#EF0107", "#EF0107"]


@pytest.mark.parametrize("missing", [None, float("nan"), ""])
def test_missing_club_colours_fall_back_to_neutral(missing):
    body, trim, _ = _fills(shirt_svg(missing, missing))
    assert body.startswith("#") and trim.startswith("#")


def test_display_name_prefers_web_name():
    assert _display_name(pd.Series({"web_name": "Saka", "player": "Bukayo Saka"})) == "Saka"
    assert _display_name(pd.Series({"web_name": None, "player": "Bukayo Saka"})) == "Bukayo Saka"


@pytest.mark.parametrize(("value", "expected"), [(34.0, "34"), (2.345, "2.35"), (0, "0")])
def test_metric_values_drop_needless_decimals(value, expected):
    assert _format_metric(value) == expected


def _gw_row(**values):
    base = {"gw_fixtures": 1, "gw_kicked_off": 0, "gw_points": None, "gw_xpts": 4.26}
    return pd.Series({**base, **values})


def test_before_kick_off_only_expected_points():
    html = gameweek_points_html(_gw_row())
    assert "4.3 xP" in html and "pts" not in html


def test_after_kick_off_actual_and_expected():
    html = gameweek_points_html(_gw_row(gw_kicked_off=1, gw_points=8))
    assert "8 pts" in html and "4.3 xP" in html


def test_captain_doubles_both():
    html = gameweek_points_html(_gw_row(gw_kicked_off=1, gw_points=8), multiplier=2)
    assert "16 pts" in html and "8.5 xP" in html


def test_blank_and_missing_expected():
    assert "Blank" in gameweek_points_html(_gw_row(gw_fixtures=0))
    assert gameweek_points_html(_gw_row(gw_xpts=float("nan"))) == ""
    assert "0 pts" in gameweek_points_html(_gw_row(gw_kicked_off=1, gw_points=float("nan"), gw_xpts=None))


def test_team_expected_points_counts_like_fpl():
    squad = pd.DataFrame({"gw_xpts": [5.0, 3.0, 2.0, 4.0], "multiplier": [2, 1, 1, 0]})  # captain, two, a sub
    assert team_expected_points(squad) == pytest.approx(15.0)
    squad["multiplier"] = [3, 1, 1, 1]  # triple captain + bench boost
    assert team_expected_points(squad) == pytest.approx(24.0)
    assert team_expected_points(squad.assign(gw_xpts=float("nan"))) is None
    assert team_expected_points(squad.drop(columns="gw_xpts")) is None
