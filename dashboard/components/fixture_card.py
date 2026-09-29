"""A player's next 5 gameweeks, colour-coded by fixture difficulty."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from theme import PAGE_BG, RADIUS_SM, TEXT_MUTED, difficulty_colour


def fixture_card(fixtures: pd.DataFrame) -> None:
    """One column per upcoming gameweek: a large tile for a single fixture,
    stacked strips for a double gameweek, and a dashed "Blank" tile when the
    team doesn't play. ``fixtures`` comes from ``queries.player_info.get_next_5``.
    """
    gameweeks = list(dict.fromkeys(fixtures["gw"]))
    for col, gw in zip(st.columns(5), gameweeks, strict=False):
        games = fixtures[(fixtures["gw"] == gw) & fixtures["opponent"].notna()].to_dict("records")
        with col:
            st.html(
                f'<div style="text-align:center;font-weight:700;font-size:12px;letter-spacing:0.04em;'
                f'color:{TEXT_MUTED};margin-bottom:8px;">GW{gw}</div>'
            )

            if not games:
                st.html(
                    f"""
                    <div style="
                        background:{PAGE_BG};
                        border:1px dashed rgba(11,11,11,0.14);
                        height:90px;
                        border-radius:{RADIUS_SM};
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        color:{TEXT_MUTED};
                        font-weight:600;
                        font-size:13px;
                    ">
                        Blank
                    </div>
                    """
                )
            elif len(games) == 1:
                fixture = games[0]
                st.html(
                    f"""
                    <div style="
                        background:{difficulty_colour(fixture["difficulty"])};
                        height:90px;
                        border-radius:{RADIUS_SM};
                        display:flex;
                        flex-direction:column;
                        align-items:center;
                        justify-content:center;
                        color:white;
                        font-weight:700;
                    ">
                        <span style="font-size:22px;">{fixture["opponent"]}</span>
                        <span style="font-size:14px;opacity:0.9;">{fixture["venue"]}</span>
                    </div>
                    """
                )
            else:
                st.html(
                    "".join(
                        f"""
                        <div style="
                            background:{difficulty_colour(fixture["difficulty"])};
                            border-radius:{RADIUS_SM};
                            display:flex;
                            align-items:center;
                            justify-content:space-between;
                            padding:4px 12px;
                            color:white;
                            font-weight:700;
                            margin-bottom:6px;
                        ">
                            <span>{fixture["opponent"]}</span>
                            <span style="opacity:0.9;">{fixture["venue"]}</span>
                        </div>
                        """
                        for fixture in games
                    )
                )
