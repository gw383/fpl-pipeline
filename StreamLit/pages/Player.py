"""Player deep-dive page: profile banner, headline metrics, and four
charts (points breakdown, radar profile, minutes donut, gameweek trend).
"""
import base64

import pandas as pd
import streamlit as st

from charts.gameweek_trend import gameweek_trend
from charts.minutes_donut import minutes_donut_chart
from charts.player_radar import player_radar
from charts.points_breakdown import points_breakdown_chart
from components.fixture_card import fixture_card
from components.metric_card import metric_card
from player_utils import news_banner_html, per_90, recommendation_stars
from queries.player_info import get_next_5, get_player_info, get_players
from queries.player_stats import get_best_stats, get_gwk, get_player_stats, get_rank_metrics, get_star

# ---------------------------------------------------------------------------
# Page config + styling
# ---------------------------------------------------------------------------

st.set_page_config(page_title="FPL Analytics", layout="wide")

st.markdown(
    """
    <style>

    .stApp {
        background-color: #f2f2f2;}

    .block-container {
        padding-top: 4rem;
        padding-left: 3rem;
        padding-right: 3rem;}

    .player-header {
        height: 100px;
        width: 100%;
        position: relative;
        background: #ffffff;
        border-radius: 0 0 20px 20px;
        overflow: hidden;
        margin-bottom: 30px;}

    .player-primary {
        position: absolute;
        width: 100%;
        height: 100%;}

    .player-secondary {
        position: absolute;
        right: 5%;
        top: 0;
        height: 100%;
        width: 15%;}

    .search-box {
        position: absolute;
        top: 25px;
        left: 40px;
        z-index: 2;}

    div[data-testid="stSelectbox"] {
        margin-top:10px;}


    /* Both dropdowns (Player and Range) */
    div[data-baseweb="select"] > div {
        background-color: #ffffff;
        border: 1px solid #d9d9d9;
        border-radius: 8px;
        box-shadow: none;}

    /* Text inside the dropdown */
    div[data-baseweb="select"] span {
        color: #222222;}

    /* Search input when typing in Player box */
    div[data-baseweb="select"] input {
        background-color: white;
        color: #222222;}

    /* Dropdown menu */
    div[role="listbox"] {
        background-color: white;
        border-radius: 8px;
        border: 1px solid #d9d9d9;}

    /* Each option */
    div[role="option"] {
        background-color: white;
        color: #222222;}

    /* Hover effect */
    div[role="option"]:hover {
        background-color: #f0f0f0;}

    /* Selected option */
    div[aria-selected="true"] {
        background-color: #e9ecef;}

    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Player + range selection
# ---------------------------------------------------------------------------

players = get_players()

if players.empty:
    # database.run_query already showed an error banner if this was a
    # connection problem; either way there's no player list to build the
    # rest of the page from.
    st.warning("No player data is available right now.")
    st.stop()

col1, col2 = st.columns([4, 1])

with col1:
    selected_player = st.selectbox("Player", players["p_full_name"])

with col2:
    range_filter = st.selectbox(
        "Range", ["All gameweeks", "Last 10 gameweeks", "Last 5 gameweeks"]
    )

player_info = get_player_info(selected_player)
next_5 = get_next_5(selected_player)
player_data = get_player_stats(selected_player, range_filter)
gwk_points = get_gwk(selected_player, range_filter)
ranks = get_rank_metrics(selected_player, range_filter)
star_ranking = get_star(selected_player)

# ---------------------------------------------------------------------------
# Bail out gracefully if any query came back empty
# ---------------------------------------------------------------------------
# Each of these is either a database problem (database.run_query already
# showed an error banner above) or a genuinely missing row for this
# player/range combination (e.g. a player with no gameweek data yet for
# "Last 5 gameweeks"). Either way, the .iloc[0] unpacking below assumes at
# least one row -- so stop here with a readable message instead of an
# IndexError crashing the whole page.
_missing = {
    "player info": player_info,
    "player stats": player_data,
    "rank metrics": ranks,
    "star rating": star_ranking,
}
_empty = [name for name, df in _missing.items() if df.empty]
if _empty:
    st.warning(
        f"No {', '.join(_empty)} available for {selected_player} "
        f"with the current range filter."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Unpack query results
# ---------------------------------------------------------------------------

info_row = player_info.iloc[0]
primary = info_row["primary"]
secondary = info_row["secondary"]
team = info_row["team"]
position = info_row["position"]
logo = info_row["image"]
form = float(info_row["form"])
price = float(info_row["price"])
creativity = float(info_row["creativity"])
# Fixed: this used to read info_row["form"] for both threat and
# influence (a copy-paste bug -- see CHANGELOG). They now read their
# own columns, which get_player_info has always selected correctly.
threat = float(info_row["threat"])
influence = float(info_row["influence"])
news = info_row["news"]
news_date = info_row["news_date"]

stat_row = player_data.iloc[0]
points = int(stat_row["points"])
minutes = int(stat_row["minutes"])
minutes_not_played = int(stat_row["minutes_not_played"])
pf_minutes = int(stat_row["pf_minutes"])
pf_cs = int(stat_row["pf_cs"])
pf_bonus = int(stat_row["pf_bonus"])
bonus = int(stat_row["bonus"])
pf_saves = int(stat_row["pf_saves"])
pf_pen_saves = int(stat_row["pf_pen_saves"])
pf_yellow = int(stat_row["pf_yellow"])
pf_red = int(stat_row["pf_red"])
pf_goals = int(stat_row["pf_goals"])
pf_assists = int(stat_row["pf_assists"])
pf_defcon = int(stat_row["pf_defcon"])
pf_own_goals = int(stat_row["pf_own_goals"])
pf_pen_missed = int(stat_row["pf_pen_missed"])
pf_goals_conceded = int(stat_row["pf_goals_conceded"])
starts = int(stat_row["starts"])
saves = int(stat_row["saves"])
defcons = int(stat_row["defcons"])
goals = int(stat_row["goals"])
clean_sheets = int(stat_row["clean_sheets"])
assists = int(stat_row["assists"])
pens_saved = int(stat_row["pens_saved"])
pens_missed = int(stat_row["pens_missed"])
goals_conceded = int(stat_row["goals_conceded"])

rank_row = ranks.iloc[0]
points_rank = int(rank_row["points_rank"])
assists_rank = int(rank_row["assists_rank"])
goals_rank = int(rank_row["goals_rank"])
bonus_rank = int(rank_row["bonus_rank"])
cs_rank = int(rank_row["cs_rank"])
saves_rank = int(rank_row["saves_rank"])
defcons_rank = int(rank_row["defcons_rank"])
dcp90_rank = int(rank_row["dcp90_rank"])
pp90_rank = int(rank_row["pp90_rank"])
saved_pens_rank = int(rank_row["saved_pens_rank"])
ppm90_rank = int(rank_row["ppm90_rank"])
ppm90_value = float(rank_row["ppm90_value"])

logo_base64 = base64.b64encode(bytes(logo)).decode()


def _num(value, cast=int):
    """Cast a query result value, defaulting to 0 for None/NaN.

    get_best_stats aggregates with MAX() and no GROUP BY, so it always
    returns exactly one row even when there's no data behind it (e.g. no
    player at this position has met the >=5-starts threshold yet) -- just
    a row of Nones/NaNs rather than an empty DataFrame. This keeps that
    case from crashing the page with `int(None)`.
    """
    return cast(value) if pd.notna(value) else cast(0)


best_stats = get_best_stats(position, range_filter)
max_row = best_stats.iloc[0] if not best_stats.empty else pd.Series(dtype=float)
max_points = _num(max_row.get("max_points"))
max_bonus = _num(max_row.get("max_bonus"))
max_goals = _num(max_row.get("max_goals"))
max_assists = _num(max_row.get("max_assists"))
max_dcp90 = _num(max_row.get("max_dcp90"), float)
max_cs = _num(max_row.get("max_cs"), float)
max_saves = _num(max_row.get("max_saves"), float)
max_pens_saved = _num(max_row.get("max_pens_saved"), float)
# Note: get_best_stats also returns max_pp90 and max_ppm90 -- neither is
# read anywhere on this page (dead computations, like the per-90 values
# cleaned up in the first refactor pass), so they're no longer unpacked
# here. The query itself is left alone since misc_sql/team_misc.sql uses
# the equivalent figures as an independent sense-check.

# Per-90 rates used by the radar chart and (for goalkeepers/outfield
# players respectively) a metric card.
saves_p90 = per_90(saves, minutes)
defcons_p90 = per_90(defcons, minutes)

star = float(star_ranking.iloc[0]["star"])
star_display = recommendation_stars(star)

# ---------------------------------------------------------------------------
# Player header banner
# ---------------------------------------------------------------------------

st.html(
    f"""
    <div class="player-header">

        <div class="player-primary" style="background:{primary};"></div>

        <!-- Player information -->
        <div style="
            position:absolute;
            left:40px;
            top:50%;
            transform:translateY(-50%);
            color:white;
            z-index:2;
        ">

            <h1 style="
                margin:0;
                font-size:38px;
                font-weight:700;
                line-height:1.05;
            ">
                {selected_player}
                <span style="
                    font-size:28px;
                    margin-left:12px;
                    letter-spacing:2px;
                ">
                    {star_display} <span style="font-size:20px;">{star:.1f}/10</span>
                </span>
            </h1>

            <p style="
                margin:4px 0 0 0;
                font-size:20px;
                font-weight:500;
                opacity:0.9;
                line-height:1.2;
            ">
                {team} • {position} • £{price}m
            </p>

        </div>

        <!-- Player news -->
        {news_banner_html(news)}

        <!-- Secondary colour / club badge -->
        <div class="player-secondary" style="
            background:{secondary};
            position:absolute;
            right:5%;
            top:0;
            height:100%;
            width:15%;
        ">

            <img
            src="data:image/png;base64,{logo_base64}"
            style="
                position:absolute;
                top:50%;
                left:50%;
                transform:translate(-50%, -50%);
                width:100px;
                height:100px;
                object-fit:contain;
            ">

        </div>

    </div>
    """
)

# ---------------------------------------------------------------------------
# Headline metric cards (goalkeepers see a save-oriented set)
# ---------------------------------------------------------------------------

st.markdown("---")

if position == "Goalkeeper":
    h1, h2, h3, h4, h5 = st.columns(5)

    with h1:
        metric_card("Points", points, points_rank)
    with h2:
        metric_card("Value (Points per million per 90)", f"{ppm90_value:.1f}%", ppm90_rank)
    with h3:
        metric_card("Saves / 90", f"{saves_p90:.1f}", saves_rank)
    with h4:
        metric_card("Penalty Saves", pens_saved, saved_pens_rank)
    with h5:
        metric_card("Clean Sheets", clean_sheets, cs_rank)
else:
    h1, h2, h3, h4, h5, h6 = st.columns(6)

    with h1:
        metric_card("Points", points, points_rank)
    with h2:
        metric_card("Value (Points per million per 90)", f"{ppm90_value:.1f}%", ppm90_rank)
    with h3:
        metric_card("Goals", goals, goals_rank)
    with h4:
        metric_card("Assists", assists, assists_rank)
    with h5:
        metric_card("DefCons / 90", f"{defcons_p90:.1f}", dcp90_rank)
    with h6:
        metric_card("Clean Sheets", clean_sheets, cs_rank)

st.markdown("---")

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

fig_breakdown, total_points_from_breakdown = points_breakdown_chart(
    pf_goals, pf_assists, pf_minutes, pf_bonus, pf_cs, pf_defcon,
    pf_saves, pf_pen_saves, pf_yellow, pf_red,
    pf_goals_conceded, pf_own_goals, pf_pen_missed,
)

fig_radar = player_radar(
    position,
    points, max_points,
    goals, max_goals,
    assists, max_assists,
    bonus, max_bonus,
    defcons_p90, max_dcp90,
    clean_sheets, max_cs,
    saves, max_saves,
    pens_saved, max_pens_saved,
    selected_player,
    primary,
)

fig_minutes = minutes_donut_chart(minutes, minutes_not_played)
fig_gameweek = gameweek_trend(gwk_points, primary)

c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.2])

with c1:
    st.plotly_chart(fig_breakdown, use_container_width=True, key="points_breakdown")
with c2:
    st.plotly_chart(fig_radar, use_container_width=True, key="player_radar")
with c3:
    st.plotly_chart(fig_minutes, use_container_width=True, key="minutes")
with c4:
    st.plotly_chart(fig_gameweek, use_container_width=True, key="gameweek_trend")

fixture_card(next_5)
