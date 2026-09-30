"""Phone layout: the HTML components carry the classes theme.py's responsive
CSS targets, and that CSS is part of the site stylesheet."""

import pandas as pd
import pytest

from components.team_fixtures import fixture_grid_header_html, fixture_grid_html, team_fixture_card
from theme import inject_base_css


def _fixtures(rows):
    return pd.DataFrame(rows, columns=["gw", "venue", "opponent", "difficulty"])


def test_site_css_includes_the_phone_rules():
    css = inject_base_css()
    assert "container-type: inline-size" in css
    assert "@media (max-width: 640px)" in css
    for key in ("st-key-sbs-", "st-key-grid2-", "st-key-metrics-"):
        assert key in css


def test_fixture_row_has_full_and_short_team_names():
    fixtures = dict(tuple(_fixtures([(7, "H", "ARS", 4), (8, "A", "CHE", 2)]).groupby("gw")))
    html = team_fixture_card("Nott'm Forest", 5, fixtures, [7, 8, 9], short_name="NFO")
    assert 'class="fpl-fdr-name"' in html and "Nott'm Forest" in html
    assert 'class="fpl-fdr-short"' in html and "NFO" in html
    # Venue shown two ways; the CSS picks one by width.
    assert "(H)" in html and ">h<" in html
    # Gameweek 9 has no fixture: a blank cell, still in the grid.
    assert html.count('class="fpl-fdr-cell"') == 3 and "Blank" in html


def test_fixture_row_short_name_falls_back_to_the_first_letters():
    html = team_fixture_card("Brentford", 12, {}, [7])
    assert "BRE" in html


def test_fixture_table_wraps_header_and_rows():
    html = fixture_grid_html(fixture_grid_header_html([7, 8]) + "<div>row</div>")
    assert html.startswith('<div class="fpl-fdr">') and "GW 7" in html and "<div>row</div>" in html


def test_next_five_is_one_grid_row_with_blank_and_double_gameweeks():
    pytest.importorskip("streamlit")
    from components.fixture_card import fixture_card_html

    html = fixture_card_html(
        _fixtures(
            [
                (7, "H", "ARS", 4),
                (8, None, None, None),  # blank
                (9, "A", "CHE", 3),  # double
                (9, "H", "LIV", 5),
                (10, "A", "EVE", 2),
                (11, "H", "BOU", 2),
            ]
        )
    )
    assert html.startswith('<div class="fpl-fx"') and "repeat(5, minmax(0, 1fr))" in html
    assert html.count('class="fpl-fx-gw"') == 5
    assert "Blank" in html
    assert html.count('class="fpl-fx-strip"') == 2


def test_stat_card_classes():
    pytest.importorskip("streamlit")
    from components.metric_card import metric_card_html

    html = metric_card_html("Points", 42, rank=3)
    for cls in ("fpl-metric", "fpl-metric-title", "fpl-metric-value", "fpl-metric-rank"):
        assert f'class="{cls}"' in html
