"""Rankings page: a bigger, per-position leaderboard than the Home
page's "Top rated players" section, which is deliberately capped at 5 a
side. This page exists to answer "who's good right now, and who
isn't" across the whole position, not just the very best -- each row
expands to the same rating breakdown used elsewhere in the app.
"""
import streamlit as st

from components.ranking_row import ranking_row_html
from components.rating_breakdown import rating_breakdown_html
from queries.player_stats import get_star_by_position
from theme import inject_base_css, masthead_html, section_header_html

st.set_page_config(page_title="FPL Analytics", page_icon="📊", layout="wide")
st.markdown(inject_base_css(), unsafe_allow_html=True)

st.html(masthead_html("Full star-rating leaderboard, position by position"))

st.html(
    section_header_html(
        "Rankings",
        "Every player's star rating within one position, best first -- the same rating "
        "as the Home page's \"Top rated players\" and the Player page, just a longer "
        "list. Click a row to see how its rating breaks down.",
    )
)

# Position label -> analytics.players.p_position id, matching the
# convention used everywhere else in this project (theme.py's
# POSITION_LABELS, player_rating.sql's p_position case statements, etc).
POSITION_OPTIONS = {
    "Goalkeepers": 1,
    "Defenders": 2,
    "Midfielders": 3,
    "Forwards": 4,
}

# How many rows to pull back per position. "All" maps to a generously
# large SQL TOP() rather than a separate no-limit query path -- there
# are only ever a few hundred players in a position at most, so "top
# (500)" is effectively "everyone" without needing different SQL.
LIMIT_OPTIONS = {
    "Top 10": 10,
    "Top 20": 20,
    "Top 30": 30,
    "Top 50": 50,
    "All": 500,
}

col1, col2 = st.columns([3, 1])
with col1:
    position_label = st.radio(
        "Position", list(POSITION_OPTIONS), horizontal=True, label_visibility="collapsed"
    )
with col2:
    limit_label = st.selectbox("Show", list(LIMIT_OPTIONS), index=2, label_visibility="collapsed")

position_id = POSITION_OPTIONS[position_label]
limit = LIMIT_OPTIONS[limit_label]

leaderboard = get_star_by_position(position_id, limit)

if leaderboard.empty:
    st.caption("No ratings available for this position right now.")
else:
    for i, (_, row) in enumerate(leaderboard.iterrows()):
        rank = i + 1
        st.html(ranking_row_html(rank, row))

        state_key = f"ranking_expanded_{position_id}_{int(row['p_id'])}"
        expanded = st.session_state.get(state_key, False)
        if st.button(
            "Hide breakdown ▴" if expanded else "Show breakdown ▾",
            key=f"btn_{state_key}",
        ):
            st.session_state[state_key] = not expanded
            expanded = not expanded
        if expanded:
            st.html(rating_breakdown_html(row, star=float(row["rating"])))

        st.html('<div style="height:6px;"></div>')
