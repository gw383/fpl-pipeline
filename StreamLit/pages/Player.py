"""Player deep-dive page: profile banner, headline metrics, and four
figures (points breakdown, radar profile, minutes meter, gameweek trend).
"""
import base64

import pandas as pd
import streamlit as st

from charts.expected_vs_actual import expected_vs_actual_chart
from charts.gameweek_trend import gameweek_trend
from charts.player_radar import player_radar
from charts.points_breakdown import points_breakdown_chart
from components.fixture_card import fixture_card
from components.metric_card import metric_card
from components.minutes_meter import minutes_meter_html
from components.rating_breakdown import rating_breakdown_html
from player_utils import news_banner_html, per_90, recommendation_stars
from queries.player_info import get_next_5, get_player_info, get_players
from queries.player_stats import get_best_stats, get_gwk, get_player_stats, get_rank_metrics, get_star
from theme import BORDER, RADIUS, SHADOW_CARD, inject_base_css, masthead_html, section_header_html

# ---------------------------------------------------------------------------
# Page config + styling
# ---------------------------------------------------------------------------

st.set_page_config(page_title="FPL Analytics", layout="wide")

st.markdown(inject_base_css(), unsafe_allow_html=True)

st.markdown(
    f"""
    <style>

    .player-header {{
        height: 140px;
        width: 100%;
        position: relative;
        background: #ffffff;
        border-radius: {RADIUS};
        overflow: hidden;
        margin-bottom: 22px;
        box-shadow: {SHADOW_CARD};
        border: 1px solid {BORDER};}}

    .player-primary {{
        position: absolute;
        width: 100%;
        height: 100%;}}

    .player-secondary {{
        position: absolute;
        right: 5%;
        top: 0;
        height: 100%;
        width: 15%;}}

    .search-box {{
        position: absolute;
        top: 25px;
        left: 40px;
        z-index: 2;}}

    </style>
    """,
    unsafe_allow_html=True,
)

st.html(masthead_html())

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
xg = float(stat_row["xg"]) if pd.notna(stat_row["xg"]) else 0.0
xa = float(stat_row["xa"]) if pd.notna(stat_row["xa"]) else 0.0
xga = float(stat_row["xga"]) if pd.notna(stat_row["xga"]) else 0.0

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
form_rank = int(rank_row["form_rank"])
# Note: get_rank_metrics also returns ppm90_rank/ppm90_value (the old
# "Value" card's rank/percentile) -- no longer unpacked here since the
# "Value" metric card they fed was replaced by "Form" below (see the
# Round 7 note by the metric-card row). The query itself is left alone
# rather than trimmed, in case a future page wants that figure back.

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
            max-width:65%;
        ">

            <h1 style="
                margin:0;
                font-size:38px;
                font-weight:700;
                line-height:1.05;
                white-space:nowrap;
                overflow:hidden;
                text-overflow:ellipsis;
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
                white-space:nowrap;
                overflow:hidden;
                text-overflow:ellipsis;
            ">
                {team} • {position} • £{price}m
            </p>

            <!-- Player news: a normal-flow line in this same block (not a
                 floating box elsewhere in the header), so it can never
                 overlap the name/team/price lines above regardless of
                 how long either one is. -->
            {news_banner_html(news)}

        </div>

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
# Rating breakdown -- same click-to-expand pattern as the Home page's
# star/differential cards (components/rating_breakdown.py), just with
# one toggle for the one player this page is already about, right under
# the header where the star itself is shown.
# ---------------------------------------------------------------------------

_breakdown_key = f"player_breakdown_{selected_player}"
_breakdown_expanded = st.session_state.get(_breakdown_key, False)
if st.button(
    "Hide rating breakdown ▴" if _breakdown_expanded else "Show rating breakdown ▾",
    key=f"btn_{_breakdown_key}",
):
    st.session_state[_breakdown_key] = not _breakdown_expanded
    _breakdown_expanded = not _breakdown_expanded
if _breakdown_expanded:
    st.html(rating_breakdown_html(star_ranking.iloc[0], star=star))

# ---------------------------------------------------------------------------
# Headline metric cards (goalkeepers see a save-oriented set)
# ---------------------------------------------------------------------------

st.html(
    section_header_html("Season snapshot", f"{range_filter.lower()} -- rank shown vs. all players in the same position.")
)

# Round 7 note: the "Value (Points per million per 90)" card used to sit
# here (h2 in both layouts below). It's been replaced with "Form" -- FPL's
# own rolling form figure (already fetched from get_player_info as `form`
# and, until now, unused anywhere on this page) -- since value-for-money
# is a budgeting question rather than a "how is this player playing right
# now" one, and this page is otherwise entirely about the latter. Price
# is still shown in the header banner above for anyone who wants to do
# their own value math.
if position == "Goalkeeper":
    h1, h2, h3, h4, h5 = st.columns(5)

    with h1:
        metric_card("Points", points, points_rank)
    with h2:
        metric_card("Form", f"{form:.1f}", form_rank)
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
        metric_card("Form", f"{form:.1f}", form_rank)
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

st.html(section_header_html("Performance breakdown"))

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

fig_gameweek = gameweek_trend(gwk_points, primary)

c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.2])

with c1, st.container(border=True):
    st.plotly_chart(fig_breakdown, use_container_width=True, key="points_breakdown")
with c2, st.container(border=True):
    st.plotly_chart(fig_radar, use_container_width=True, key="player_radar")
with c3, st.container(border=True):
    # A meter, not a chart -- "minutes played vs. minutes not played"
    # is a single ratio against a limit, which reads faster as a meter
    # than as a 2-slice donut (see components/minutes_meter.py).
    st.html(minutes_meter_html(minutes, minutes_not_played))
with c4, st.container(border=True):
    st.plotly_chart(fig_gameweek, use_container_width=True, key="gameweek_trend")

# ---------------------------------------------------------------------------
# Expected vs actual (is this player lucky or clinical?)
# ---------------------------------------------------------------------------

st.html(
    section_header_html(
        "Process vs outcome",
        "Actual output next to the underlying expected numbers (xG/xA/xGA) -- "
        "a player consistently ahead of their expected figures is finishing "
        "chances well rather than just running hot.",
    )
)

with st.container(border=True):
    fig_expected = expected_vs_actual_chart(goals, xg, assists, xa, goals_conceded, xga, position)
    st.plotly_chart(fig_expected, use_container_width=True, key="expected_vs_actual")

st.html(section_header_html("Upcoming fixtures"))

with st.container(border=True):
    fixture_card(next_5)
