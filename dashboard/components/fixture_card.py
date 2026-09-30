"""A player's next 5 gameweeks, colour-coded by fixture difficulty."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from theme import PAGE_BG, RADIUS_SM, TEXT_MUTED, difficulty_colour


def _gameweek_html(gw, games: list[dict]) -> str:
    """One column: the "GWn" label over a tile (single fixture), stacked
    strips (double gameweek) or a dashed "Blank" tile."""
    label = (
        f'<div class="fpl-fx-gw" style="text-align:center;font-weight:700;font-size:12px;letter-spacing:0.04em;'
        f'color:{TEXT_MUTED};margin-bottom:8px;white-space:nowrap;">GW{gw}</div>'
    )
    if not games:
        body = f"""
        <div class="fpl-fx-tile fpl-fx-blank" style="background:{PAGE_BG};border:1px dashed rgba(11,11,11,0.14);
                    height:90px;border-radius:{RADIUS_SM};display:flex;align-items:center;justify-content:center;
                    color:{TEXT_MUTED};font-weight:600;font-size:13px;box-sizing:border-box;">
            Blank
        </div>
        """
    elif len(games) == 1:
        fixture = games[0]
        body = f"""
        <div class="fpl-fx-tile" style="background:{difficulty_colour(fixture["difficulty"])};height:90px;
                    border-radius:{RADIUS_SM};display:flex;flex-direction:column;align-items:center;
                    justify-content:center;color:white;font-weight:700;">
            <span class="fpl-fx-opp" style="font-size:22px;">{fixture["opponent"]}</span>
            <span class="fpl-fx-venue" style="font-size:14px;opacity:0.9;">{fixture["venue"]}</span>
        </div>
        """
    else:
        body = "".join(
            f"""
            <div class="fpl-fx-strip" style="background:{difficulty_colour(fixture["difficulty"])};
                        border-radius:{RADIUS_SM};display:flex;align-items:center;justify-content:space-between;
                        padding:4px 12px;color:white;font-weight:700;margin-bottom:6px;white-space:nowrap;
                        overflow:hidden;">
                <span>{fixture["opponent"]}</span>
                <span style="opacity:0.9;">{fixture["venue"]}</span>
            </div>
            """
            for fixture in games
        )
    return f'<div style="min-width:0;">{label}{body}</div>'


def fixture_card_html(fixtures: pd.DataFrame) -> str:
    """The five gameweeks as one grid, so they stay in a row at any width
    (theme.py shrinks the tiles in narrow containers)."""
    gameweeks = list(dict.fromkeys(fixtures["gw"]))[:5]
    columns = "".join(
        _gameweek_html(gw, fixtures[(fixtures["gw"] == gw) & fixtures["opponent"].notna()].to_dict("records"))
        for gw in gameweeks
    )
    return (
        '<div class="fpl-fx" style="display:grid;grid-template-columns:repeat(5, minmax(0, 1fr));gap:12px;">'
        f"{columns}</div>"
    )


def fixture_card(fixtures: pd.DataFrame) -> None:
    """One column per upcoming gameweek: a large tile for a single fixture,
    stacked strips for a double gameweek, and a dashed "Blank" tile when the
    team doesn't play. ``fixtures`` comes from ``queries.player_info.get_next_5``.
    """
    st.html(fixture_card_html(fixtures))
