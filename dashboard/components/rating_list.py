"""A compact ranked list of players, each expandable to its rating breakdown."""

import pandas as pd
import streamlit as st

from components.rating_breakdown import rating_breakdown_html
from theme import POSITION_COLOURS, TEXT_MUTED


def rating_list(players: pd.DataFrame, label: str, position_id: int) -> None:
    """``players`` comes from ``queries.player_stats.get_top_rated``."""
    st.html(
        f'<div style="display:flex;align-items:center;gap:8px;font-size:12px;font-weight:700;'
        f'letter-spacing:0.06em;text-transform:uppercase;color:{TEXT_MUTED};margin:0 0 8px 2px;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:{POSITION_COLOURS[position_id]};"></span>'
        f"{label}</div>"
    )
    if players.empty:
        st.caption("No ratings available.")
    for rank, (_, row) in enumerate(players.iterrows(), start=1):
        name = row["web_name"] if pd.notna(row.get("web_name")) else row["player"]
        team = f" ({row['team_short_name']})" if pd.notna(row.get("team_short_name")) else ""
        with st.expander(f"{rank}.\u2002**{name}**{team}\u2002·\u2002{row['rating']:.1f}"):
            st.html(rating_breakdown_html(row, star=float(row["rating"])))
