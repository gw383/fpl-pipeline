"""Tests for the team-sheet helpers in dashboard/components/pitch.py."""

import base64
import re

import pandas as pd
import pytest

from components.pitch import _display_name, _format_metric, shirt_svg


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
