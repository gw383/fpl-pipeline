"""Player comparison page: two players' profile pages side by side, so
choosing between two transfer targets doesn't mean flipping back and
forth on the Player page.

Deliberately built as its own page rather than a refactor of
pages/Player.py -- it reuses the same lower-level, already-tested
pieces (metric_card, rating_breakdown_html, news_banner_html,
fixture_card, and the same queries Player.py already calls) but writes
its own, more compact header layout suited to sitting in a half-width
column, so Player.py itself needed zero changes and carries zero risk
of a regression from this addition.

Per feedback, this deliberately EXCLUDES the four chart figures (points
breakdown, radar, minutes meter, gameweek trend) and the process-vs-
outcome chart that Player.py shows -- two full chart rows side by side
would be a lot of squeezed, hard-to-read visual noise for what this page
is actually for (a quick side-by-side read of the numbers), and the
same charts are always one click away on the Player page for either
player if a closer look is wanted.
"""
import base64

import streamlit as st

from components.fixture_card import fixture_card
from components.metric_card import metric_card
from components.rating_breakdown import rating_breakdown_html
from player_utils import news_banner_html, per_90, recommendation_stars
from queries.player_info import get_next_5, get_player_info, get_players
from queries.player_stats import get_player_stats, get_rank_metrics, get_star
from theme import BORDER, RADIUS, SHADOW_CARD, inject_base_css, masthead_html, section_header_html

st.set_page_config(page_title="FPL Analytics", page_icon="⚖️", layout="wide")
st.markdown(inject_base_css(), unsafe_allow_html=True)

st.html(masthead_html("Compare two players' profiles side by side"))

# ---------------------------------------------------------------------------
# Player + range selection
# ---------------------------------------------------------------------------

players = get_players()

if players.empty:
    st.warning("No player data is available right now.")
    st.stop()

names = list(players["p_full_name"])

col_a, col_b, col_range = st.columns([2, 2, 1])
with col_a:
    player_a = st.selectbox("Player A", names, index=0, key="compare_player_a")
with col_b:
    # Defaults to the second name in the list (rather than the same
    # index as Player A) so the page doesn't open comparing a player
    # against themselves.
    default_b_index = 1 if len(names) > 1 else 0
    player_b = st.selectbox("Player B", names, index=default_b_index, key="compare_player_b")
with col_range:
    range_filter = st.selectbox(
        "Range", ["All gameweeks", "Last 10 gameweeks", "Last 5 gameweeks"], key="compare_range"
    )

st.markdown("---")


# ---------------------------------------------------------------------------
# One player's profile column
# ---------------------------------------------------------------------------


def _compact_header_html(selected_player: str, info_row, star: float) -> str:
    """A shorter version of Player.py's header banner, sized to sit in a
    half-width column rather than a full-width page.
    """
    team = info_row["team"]
    position = info_row["position"]
    price = float(info_row["price"])
    primary = info_row["primary"]
    secondary = info_row["secondary"]
    logo_base64 = base64.b64encode(bytes(info_row["image"])).decode()
    news = info_row["news"]
    star_display = recommendation_stars(star)

    return f"""
    <div style="
        height:120px;
        width:100%;
        position:relative;
        background:{primary};
        border-radius:{RADIUS};
        overflow:hidden;
        margin-bottom:14px;
        box-shadow:{SHADOW_CARD};
        border:1px solid {BORDER};
    ">
        <div style="
            position:absolute;
            left:22px;
            top:50%;
            transform:translateY(-50%);
            color:white;
            z-index:2;
            max-width:70%;
        ">
            <h2 style="
                margin:0;
                font-size:24px;
                font-weight:700;
                line-height:1.15;
                white-space:nowrap;
                overflow:hidden;
                text-overflow:ellipsis;
            ">
                {selected_player}
            </h2>
            <div style="font-size:16px;letter-spacing:1px;margin-top:2px;">
                {star_display} <span style="font-size:14px;">{star:.1f}/10</span>
            </div>
            <p style="
                margin:4px 0 0 0;
                font-size:14px;
                font-weight:500;
                opacity:0.9;
                white-space:nowrap;
                overflow:hidden;
                text-overflow:ellipsis;
            ">
                {team} • {position} • £{price}m
            </p>
            {news_banner_html(news)}
        </div>
        <div style="
            position:absolute;
            right:4%;
            top:0;
            height:100%;
            width:20%;
            background:{secondary};
        ">
            <img
            src="data:image/png;base64,{logo_base64}"
            style="
                position:absolute;
                top:50%;
                left:50%;
                transform:translate(-50%, -50%);
                width:64px;
                height:64px;
                object-fit:contain;
            ">
        </div>
    </div>
    """


def render_player_column(selected_player: str, key_prefix: str) -> None:
    """Render one full player profile (header, star breakdown, season
    snapshot, upcoming fixtures) into whatever container is currently
    active -- called once per side of the st.columns(2) comparison
    layout below.
    """
    player_info = get_player_info(selected_player)
    player_data = get_player_stats(selected_player, range_filter)
    ranks = get_rank_metrics(selected_player, range_filter)
    star_ranking = get_star(selected_player)
    next_5 = get_next_5(selected_player)

    missing = [
        name
        for name, df in {
            "player info": player_info,
            "player stats": player_data,
            "rank metrics": ranks,
            "star rating": star_ranking,
        }.items()
        if df.empty
    ]
    if missing:
        st.warning(
            f"No {', '.join(missing)} available for {selected_player} "
            f"with the current range filter."
        )
        return

    info_row = player_info.iloc[0]
    position = info_row["position"]
    form = float(info_row["form"])

    stat_row = player_data.iloc[0]
    points = int(stat_row["points"])
    minutes = int(stat_row["minutes"])
    goals = int(stat_row["goals"])
    assists = int(stat_row["assists"])
    clean_sheets = int(stat_row["clean_sheets"])
    saves = int(stat_row["saves"])
    defcons = int(stat_row["defcons"])
    pens_saved = int(stat_row["pens_saved"])

    rank_row = ranks.iloc[0]
    points_rank = int(rank_row["points_rank"])
    form_rank = int(rank_row["form_rank"])
    goals_rank = int(rank_row["goals_rank"])
    assists_rank = int(rank_row["assists_rank"])
    cs_rank = int(rank_row["cs_rank"])
    saves_rank = int(rank_row["saves_rank"])
    dcp90_rank = int(rank_row["dcp90_rank"])
    saved_pens_rank = int(rank_row["saved_pens_rank"])

    saves_p90 = per_90(saves, minutes)
    defcons_p90 = per_90(defcons, minutes)

    star = float(star_ranking.iloc[0]["star"])

    st.html(_compact_header_html(selected_player, info_row, star))

    breakdown_key = f"{key_prefix}_breakdown_{selected_player}"
    expanded = st.session_state.get(breakdown_key, False)
    if st.button(
        "Hide rating breakdown ▴" if expanded else "Show rating breakdown ▾",
        key=f"btn_{breakdown_key}",
    ):
        st.session_state[breakdown_key] = not expanded
        expanded = not expanded
    if expanded:
        st.html(rating_breakdown_html(star_ranking.iloc[0], star=star))

    # Season-snapshot metric cards -- same GK-vs-outfield split as
    # pages/Player.py, just 2-per-row instead of 5/6-per-row so they fit
    # a half-width column without crowding.
    if position == "Goalkeeper":
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)
        with r1c1:
            metric_card("Points", points, points_rank)
        with r1c2:
            metric_card("Form", f"{form:.1f}", form_rank)
        with r2c1:
            metric_card("Saves / 90", f"{saves_p90:.1f}", saves_rank)
        with r2c2:
            metric_card("Clean Sheets", clean_sheets, cs_rank)
        r3c1, _r3c2 = st.columns(2)
        with r3c1:
            metric_card("Penalty Saves", pens_saved, saved_pens_rank)
    else:
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)
        r3c1, r3c2 = st.columns(2)
        with r1c1:
            metric_card("Points", points, points_rank)
        with r1c2:
            metric_card("Form", f"{form:.1f}", form_rank)
        with r2c1:
            metric_card("Goals", goals, goals_rank)
        with r2c2:
            metric_card("Assists", assists, assists_rank)
        with r3c1:
            metric_card("DefCons / 90", f"{defcons_p90:.1f}", dcp90_rank)
        with r3c2:
            metric_card("Clean Sheets", clean_sheets, cs_rank)

    st.html(section_header_html("Upcoming fixtures"))
    with st.container(border=True):
        fixture_card(next_5)


# ---------------------------------------------------------------------------
# Side-by-side layout
# ---------------------------------------------------------------------------

left, right = st.columns(2, gap="large")

with left:
    render_player_column(player_a, "a")

with right:
    render_player_column(player_b, "b")
