import streamlit as st
import pandas as pd
import base64
import plotly.express as px
from queries.player_info import (
    get_players,
    get_player_info)
from queries.player_stats import (
    get_player_stats,
    get_best_stats,
    get_rank_metrics,
    get_gwk)
from database import engine
from charts.points_breakdown import points_breakdown_chart
from charts.player_radar import player_radar
from charts.minutes_donut import minutes_donut_chart
from charts.gameweek_trend import gameweek_trend
from components.metric_card import metric_card

# Config
st.set_page_config(
    page_title="FPL Analytics",
    layout="wide")

# Custom CSS
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
unsafe_allow_html=True)


# Query imports and definining columns

players = get_players()

col1, col2 = st.columns([4, 1])

with col1:
    selected_player = st.selectbox(
        "Player",
        players["p_full_name"])

with col2:
    range_filter = st.selectbox(
        "Range",
        ["All gameweeks", "Last 10 gameweeks", "Last 5 gameweeks"])


player_info = get_player_info(
    selected_player)

player_data = get_player_stats(
    selected_player,
    range_filter)

gwk_points = get_gwk(
    selected_player,
    range_filter)

ranks = get_rank_metrics(
    selected_player,
    range_filter)


primary = player_info.iloc[0]["primary"]
secondary = player_info.iloc[0]["secondary"]
team = player_info.iloc[0]["team"]
position = player_info.iloc[0]["position"]
logo = player_info.iloc[0]["image"]
form = float(player_info.iloc[0]["form"])
price = float(player_info.iloc[0]["price"])
creativity = float(player_info.iloc[0]["creativity"])
threat = float(player_info.iloc[0]["form"])
influence = float(player_info.iloc[0]["form"])
news = player_info.iloc[0]["news"]
news_date = player_info.iloc[0]["news_date"]



points = int(player_data.iloc[0]["points"])
minutes = int(player_data.iloc[0]["minutes"])
minutes_not_played = int(player_data.iloc[0]["minutes_not_played"])
pf_minutes = int(player_data.iloc[0]["pf_minutes"])
pf_cs = int(player_data.iloc[0]["pf_cs"])
pf_bonus = int(player_data.iloc[0]["pf_bonus"])
bonus = int(player_data.iloc[0]["bonus"])
pf_saves = int(player_data.iloc[0]["pf_saves"])
pf_pen_saves = int(player_data.iloc[0]["pf_pen_saves"])
pf_yellow = int(player_data.iloc[0]["pf_yellow"])
pf_red = int(player_data.iloc[0]["pf_red"])
pf_goals = int(player_data.iloc[0]["pf_goals"])
pf_assists = int(player_data.iloc[0]["pf_assists"])
pf_defcon = int(player_data.iloc[0]["pf_defcon"])
pf_own_goals = int(player_data.iloc[0]["pf_own_goals"])
pf_pen_missed = int(player_data.iloc[0]["pf_pen_missed"])
pf_goals_conceded = int(player_data.iloc[0]["pf_goals_conceded"])
starts = int(player_data.iloc[0]["starts"])
saves = int(player_data.iloc[0]["saves"])
defcons = int(player_data.iloc[0]["defcons"])
goals = int(player_data.iloc[0]["goals"])
clean_sheets = int(player_data.iloc[0]["clean_sheets"])
assists = int(player_data.iloc[0]["assists"])
pens_saved = int(player_data.iloc[0]["pens_saved"])
pens_missed = int(player_data.iloc[0]["pens_missed"])
goals_conceded = int(player_data.iloc[0]["goals_conceded"])

points_rank = int(ranks.iloc[0]["points_rank"])
assists_rank = int(ranks.iloc[0]["assists_rank"])
goals_rank = int(ranks.iloc[0]["goals_rank"])
bonus_rank = int(ranks.iloc[0]["bonus_rank"])
cs_rank = int(ranks.iloc[0]["cs_rank"])
saves_rank = int(ranks.iloc[0]["saves_rank"])
defcons_rank = int(ranks.iloc[0]["defcons_rank"])
dcp90_rank = int(ranks.iloc[0]["dcp90_rank"])
pp90_rank = int(ranks.iloc[0]["pp90_rank"])
saved_pens_rank = int(ranks.iloc[0]["saved_pens_rank"])
ppm90_rank = int(ranks.iloc[0]["ppm90_rank"])
ppm90_value = float(ranks.iloc[0]["ppm90_value"])

logo_base64 = base64.b64encode(bytes(logo)).decode()

max_stats = get_best_stats(position, range_filter)

max_points = int(max_stats.iloc[0]["max_points"])
max_bonus = int(max_stats.iloc[0]["max_bonus"])
max_goals = int(max_stats.iloc[0]["max_goals"])
max_assists = int(max_stats.iloc[0]["max_assists"])
max_dcp90 = float(max_stats.iloc[0]["max_dcp90"])
max_pp90 = float(max_stats.iloc[0]["max_pp90"])
max_cs = float(max_stats.iloc[0]["max_cs"])
max_saves = float(max_stats.iloc[0]["max_saves"])
max_pens_saved = float(max_stats.iloc[0]["max_pens_saved"])
max_ppm90 = float(max_stats.iloc[0]["max_ppm90"])

if minutes == 0:
    points_pmp90 = 0
else: points_pmp90 = round((points * 90 / minutes) / price, 2)

if minutes == 0:
    player_pp90 = 0
else: player_pp90 = round(points * 90 / minutes, 1)

if minutes == 0:
    saves_p90 = 0
else: saves_p90 = round(saves * 90 / minutes, 1)

if minutes == 0: assists_p90 = 0
else: assists_p90 = round(assists * 90 / minutes, 1)

if minutes == 0:
    goals_p90 = 0
else: goals_p90 = round(goals * 90 / minutes, 1)

if minutes == 0:
    defcons_p90 = 0
else: defcons_p90 = round(defcons * 90 / minutes, 1)

if minutes == 0:
    clean_sheets_p90 = 0
else: clean_sheets_p90 = round(clean_sheets * 90 / minutes, 1)

# Player banner

if pd.isna(news) or not news:
    news_html = ""

elif "25%" in str(news):
    news_html = f"""
    <div style="
        position:absolute;
        left:48%;
        right:21%;
        top:50%;
        transform:translateY(-50%);
        color:#222;
        font-size:17px;
        font-weight:600;
        line-height:1.35;
        z-index:2;
        background:#fff3b0;
        padding:10px 16px;
        border-radius:12px;
        width:max-content;
        max-width:45%;
    ">
        ⚠️ {news}
    </div>
    """

elif "50%" in str(news):
    news_html = f"""
    <div style="
        position:absolute;
        left:48%;
        right:21%;
        top:50%;
        transform:translateY(-50%);
        color:#222;
        font-size:17px;
        font-weight:600;
        line-height:1.35;
        z-index:2;
        background:#ffd08a;
        padding:10px 16px;
        border-radius:12px;
        width:max-content;
        max-width:45%;
    ">
        ⚠️ {news}
    </div>
    """

elif "75%" in str(news):
    news_html = f"""
    <div style="
        position:absolute;
        left:48%;
        right:21%;
        top:50%;
        transform:translateY(-50%);
        color:#222;
        font-size:17px;
        font-weight:600;
        line-height:1.35;
        z-index:2;
        background:#e8903a;
        padding:10px 16px;
        border-radius:12px;
        width:max-content;
        max-width:45%;
    ">
        ⚠️ {news}
    </div>
    """

else:
    news_html = f"""
    <div style="
        position:absolute;
        left:48%;
        right:21%;
        top:50%;
        transform:translateY(-50%);
        color:#fff;
        font-size:17px;
        font-weight:600;
        line-height:1.35;
        z-index:2;
        background:#d9534f;
        padding:10px 16px;
        border-radius:12px;
        width:max-content;
        max-width:45%;
    ">
        ⚠️ {news}
    </div>
    """

st.html(
f"""
<div class="player-header">

    <div class="player-primary"
    style="
        background:{primary};
    ">
    </div>

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
    {news_html}

    <!-- Secondary colour / club badge -->
    <div class="player-secondary"
    style="
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

# Player summary via metric card
st.markdown("---")

if position == "Goalkeeper":

    h1, h2, h3, h4, h5 = st.columns(5)
    
    saves_p90 = round(saves * 90 / minutes, 1) if minutes > 0 else 0

    with h1:
        metric_card(
            "Points",
            points,
            points_rank)
    with h2:
        metric_card(
            "Value (Points per million per 90)",
            f"{ppm90_value:.1f}%",
            ppm90_rank)
    with h3:
        metric_card(
            "Saves / 90",
            f"{saves_p90:.1f}",
            saves_rank)
    with h4:
        metric_card(
            "Penalty Saves",
            pens_saved,
            saved_pens_rank)
    with h5:
        metric_card(
            "Clean Sheets",
            clean_sheets,
            cs_rank)
else:
    h1, h2, h3, h4, h5, h6 = st.columns(6)

    defcons_p90 = round(defcons * 90 / minutes, 1) if minutes > 0 else 0

    with h1:
        metric_card(
            "Points",
            points,
            points_rank)
    with h2:
        metric_card(
            "Value (Points per million per 90)",
            f"{ppm90_value:.1f}%",
            ppm90_rank)
    with h3:
        metric_card(
            "Goals",
            goals,
            goals_rank)
    with h4:
        metric_card(
            "Assists",
            assists,
            assists_rank)
    with h5:
        metric_card(
            "DefCons / 90",
            f"{defcons_p90:.1f}",
            dcp90_rank)
    with h6:
        metric_card(
            "Clean Sheets",
            clean_sheets,
            cs_rank)

st.markdown("---")

# Importing chart templates
fig_breakdown, total_points_from_breakdown = points_breakdown_chart(
    pf_goals,
    pf_assists,
    pf_minutes,
    pf_bonus,
    pf_cs,
    pf_defcon,
    pf_saves,
    pf_pen_saves,
    pf_yellow,
    pf_red,
    pf_goals_conceded,
    pf_own_goals,
    pf_pen_missed)

fig_radar = player_radar(
    position,
    points,
    max_points,
    goals,
    max_goals,
    assists,
    max_assists,
    bonus,
    max_bonus,
    defcons_p90,
    max_dcp90,
    clean_sheets,
    max_cs,
    saves,
    max_saves,
    pens_saved,
    max_pens_saved,
    selected_player,
    primary
)

fig_minutes = minutes_donut_chart(
    minutes,
    minutes_not_played)

fig_gameweek = gameweek_trend(
    gwk_points,
    primary)

# Adding charts to dashboard
c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.2])

with c1:
    st.plotly_chart(
        fig_breakdown,
        use_container_width=True,
        key="points_breakdown")

with c2:
    st.plotly_chart(
        fig_radar,
        use_container_width=True,
        key="player_radar")

with c3:
    st.plotly_chart(
        fig_minutes,
        use_container_width=True,
        key="minutes")

with c4:
    st.plotly_chart(
        fig_gameweek,
        use_container_width=True,
        key="gameweek_trend")


