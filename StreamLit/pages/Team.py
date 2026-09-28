"""Team page: pick a team and a gameweek range (the same "All/Last 10/
Last 5 gameweeks" range used on the Player page), see that team's
league position and colours, how their results in that range rank
against every other team, a game-by-game form guide, and each result
in full -- score, goalscorers, assisters, and the underlying xG/xA/xGA
behind it.
"""
import base64

import pandas as pd
import streamlit as st

from components.metric_card import metric_card
from components.team_result_card import team_result_card
from queries.team_results import (
    build_contributor_strings,
    get_team_contributors,
    get_team_profile,
    get_team_rank_metrics,
    get_team_results,
    get_teams,
)
from theme import (
    BORDER,
    RADIUS,
    SHADOW_CARD,
    STATUS_CRITICAL,
    STATUS_GOOD,
    STATUS_WARNING,
    TEXT_MUTED,
    inject_base_css,
    masthead_html,
    section_header_html,
)

_RESULT_COLOUR = {"W": STATUS_GOOD, "D": STATUS_WARNING, "L": STATUS_CRITICAL}

# ---------------------------------------------------------------------------
# Page config + styling
# ---------------------------------------------------------------------------

st.set_page_config(page_title="FPL Analytics", page_icon="🛡️", layout="wide")
st.markdown(inject_base_css(), unsafe_allow_html=True)

st.markdown(
    f"""
    <style>

    .team-header {{
        height: 120px;
        width: 100%;
        position: relative;
        background: #ffffff;
        border-radius: {RADIUS};
        overflow: hidden;
        margin-bottom: 22px;
        box-shadow: {SHADOW_CARD};
        border: 1px solid {BORDER};}}

    .team-primary {{
        position: absolute;
        width: 100%;
        height: 100%;}}

    .team-secondary {{
        position: absolute;
        right: 5%;
        top: 0;
        height: 100%;
        width: 15%;}}

    </style>
    """,
    unsafe_allow_html=True,
)

st.html(masthead_html())

# ---------------------------------------------------------------------------
# Team + range selection
# ---------------------------------------------------------------------------

teams = get_teams()

if teams.empty:
    # database.run_query already showed an error banner above if this was
    # a connection problem; either way there's no team list to build the
    # rest of the page from.
    st.warning("No team data is available right now.")
    st.stop()

col1, col2 = st.columns([4, 1])

with col1:
    selected_team = st.selectbox("Team", teams["team_name"])

with col2:
    range_filter = st.selectbox(
        "Range", ["All gameweeks", "Last 10 gameweeks", "Last 5 gameweeks"]
    )

team_profile = get_team_profile(selected_team)
team_results = get_team_results(selected_team, range_filter)
contributors = get_team_contributors(selected_team, range_filter)
rank_metrics = get_team_rank_metrics(selected_team, range_filter)

if team_profile.empty:
    st.warning(f"No profile data available for {selected_team}.")
    st.stop()

# ---------------------------------------------------------------------------
# Header banner
# ---------------------------------------------------------------------------

profile_row = team_profile.iloc[0]
primary = profile_row["primary"]
secondary = profile_row["secondary"]
logo = profile_row["image"]
table_position = int(profile_row["team_table_position"])
logo_base64 = base64.b64encode(bytes(logo)).decode()


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


st.html(
    f"""
    <div class="team-header">

        <div class="team-primary" style="background:{primary};"></div>

        <div style="
            position:absolute;
            left:40px;
            top:50%;
            transform:translateY(-50%);
            color:white;
            z-index:2;
            max-width:65%;
        ">
            <h1 style="
                margin:0;
                font-size:34px;
                font-weight:700;
                line-height:1.05;
                white-space:nowrap;
                overflow:hidden;
                text-overflow:ellipsis;
            ">
                {selected_team}
            </h1>
            <p style="
                margin:4px 0 0 0;
                font-size:18px;
                font-weight:500;
                opacity:0.9;
            ">
                {table_position}{ordinal(table_position)} in the table
            </p>
        </div>

        <div class="team-secondary" style="background:{secondary};">
            <img
            src="data:image/png;base64,{logo_base64}"
            style="
                position:absolute;
                top:50%;
                left:50%;
                transform:translate(-50%, -50%);
                width:80px;
                height:80px;
                object-fit:contain;
            ">
        </div>

    </div>
    """
)

# ---------------------------------------------------------------------------
# Range snapshot -- same metric_card + row_number()-ranked pattern the
# Player page uses (queries.player_stats.get_rank_metrics), just ranked
# against the other 19 teams over the same range instead of against
# same-position players.
# ---------------------------------------------------------------------------

st.html(
    section_header_html(
        "Range snapshot",
        f"{range_filter.lower()} -- rank shown vs. all 20 teams over the same range.",
    )
)

if rank_metrics.empty:
    st.info(f"{selected_team} haven't played any finished fixtures in this range yet.")
else:
    rank_row = rank_metrics.iloc[0]
    games_played = int(rank_row["games_played"])
    wins = int(rank_row["wins"])
    draws = int(rank_row["draws"])
    losses = int(rank_row["losses"])

    st.caption(f"Based on {games_played} finished game{'s' if games_played != 1 else ''} in this range.")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        metric_card("Record (W-D-L)", f"{wins}-{draws}-{losses}", int(rank_row["form_points_rank"]))
    with m2:
        metric_card("Goals scored", int(rank_row["goals_scored"]), int(rank_row["goals_scored_rank"]))
    with m3:
        metric_card("Goals conceded", int(rank_row["goals_conceded"]), int(rank_row["goals_conceded_rank"]))
    with m4:
        metric_card("Clean sheets", int(rank_row["clean_sheets"]), int(rank_row["clean_sheets_rank"]))
    with m5:
        metric_card("xG", f"{rank_row['total_xg']:.1f}", int(rank_row["xg_rank"]))
    with m6:
        metric_card("xGA", f"{rank_row['total_xga']:.1f}", int(rank_row["xga_rank"]))

st.markdown("---")

# ---------------------------------------------------------------------------
# Form guide -- a quick left-to-right (oldest to most recent) strip of
# W/D/L badges, built from the same team_results rows the cards below
# use, so it costs no extra query.
# ---------------------------------------------------------------------------

st.html(section_header_html("Results", "Most recent gameweek first below; form guide reads oldest to newest, left to right."))

if team_results.empty:
    st.caption(f"No finished fixtures for {selected_team} in this range yet.")
    st.stop()

chronological = team_results.sort_values("gw_id")
form_chips = "".join(
    f"""
    <div style="
        width:26px;height:26px;border-radius:999px;
        background:{_RESULT_COLOUR.get(row['result'], STATUS_WARNING)};
        color:white;font-size:12px;font-weight:800;
        display:flex;align-items:center;justify-content:center;
        flex-shrink:0;
    " title="GW{int(row['gw_id'])} vs {row['opponent']}: {row['own_score']}-{row['opp_score']}">
        {row['result']}
    </div>
    """
    for _, row in chronological.iterrows()
)
st.html(f'<div style="display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap;">{form_chips}</div>')

# ---------------------------------------------------------------------------
# Result cards, most recent first
# ---------------------------------------------------------------------------

contributor_strings = build_contributor_strings(contributors)

for _, row in team_results.iterrows():
    gw_id = int(row["gw_id"])
    goalscorers, assisters = contributor_strings.get(gw_id, ("", ""))
    st.html(team_result_card(row, goalscorers, assisters))
