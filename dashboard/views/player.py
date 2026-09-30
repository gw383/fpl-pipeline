"""Player profile: rating and its breakdown, headline stats ranked within the
position, points breakdown, trend, radar, minutes, actual vs expected output
and upcoming fixtures."""

import pandas as pd
import streamlit as st

from charts.expected_vs_actual import expected_vs_actual_chart
from charts.gameweek_trend import gameweek_trend
from charts.player_radar import player_radar
from charts.points_breakdown import points_breakdown_chart
from components.banner import banner_stars_html, club_banner_html
from components.card import card
from components.fixture_card import fixture_card
from components.metric_card import metric_row
from components.minutes_meter import minutes_meter_html
from components.rating_breakdown import rating_breakdown_html
from formatting import news_banner_html, per_90
from queries.common import RANGE_OPTIONS
from queries.player_info import get_next_5, get_player_info, get_players
from queries.player_stats import get_best_stats, get_gameweek_points, get_player_stats, get_rank_metrics, get_star
from theme import card_title_html, page_header_html, section_header_html

st.html(page_header_html("Player profiles", "How any player is performing, and how their rating is built."))

players = get_players()
if players.empty:
    st.warning("No player data is available right now.")
    st.stop()

names = dict(zip(players["p_id"], players["p_full_name"]))
col1, col2 = st.columns([4, 1])
with col1:
    player_id = st.selectbox("Player", list(names), format_func=names.get)
with col2:
    range_label = st.selectbox("Range", list(RANGE_OPTIONS))
player_name = names[player_id]

info = get_player_info(player_id)
stats = get_player_stats(player_id, range_label)
ranks = get_rank_metrics(player_id, range_label)
rating = get_star(player_id)

missing = [
    label
    for label, df in {"player info": info, "player stats": stats, "rank metrics": ranks, "star rating": rating}.items()
    if df.empty
]
if missing:
    st.warning(f"No {', '.join(missing)} available for {player_name} with the current range filter.")
    st.stop()

info_row = info.iloc[0]
stat = stats.iloc[0].fillna(0)
rank = ranks.iloc[0]
rating_row = rating.iloc[0]
position = info_row["position"]
star = float(rating_row["star"])
team_colour = info_row["primary_colour"]

best = get_best_stats(position, range_label)
best_row = best.iloc[0].fillna(0) if not best.empty else pd.Series(dtype=float)

minutes = int(stat["minutes"])
saves_p90 = per_90(stat["saves"], minutes)
defcons_p90 = per_90(stat["defcons"], minutes)

# ---------------------------------------------------------------------------
# Header and rating breakdown
# ---------------------------------------------------------------------------

st.html(
    club_banner_html(
        f"""
        <div class="fpl-banner-title" style="font-size:36px;font-weight:800;line-height:1.05;letter-spacing:-0.02em;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{player_name}</div>
        <div style="margin-top:8px;">{banner_stars_html(star, team_colour)}</div>
        <div class="fpl-banner-meta" style="margin-top:6px;font-size:17px;font-weight:500;opacity:0.9;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
            {info_row["team"]} &middot; {position} &middot; £{info_row["price"]}m
        </div>
        {news_banner_html(info_row["news"])}
        """,
        team_colour,
        info_row["secondary_colour"],
        info_row["badge_file"],
        size="large",
    )
)

with st.expander("Expected points breakdown"):
    st.html(rating_breakdown_html(rating_row, star=star))

# ---------------------------------------------------------------------------
# Headline stats (goalkeepers get a save-oriented set)
# ---------------------------------------------------------------------------

st.html(
    section_header_html("Season snapshot", f"{range_label} · the pill shows the rank among all {position.lower()}s.")
)
form = f"{float(info_row['form']):.1f}"
if position == "Goalkeeper":
    cards = [
        ("Points", int(stat["points"]), rank["points_rank"]),
        ("Form", form, rank["form_rank"]),
        ("Saves / 90", f"{saves_p90:.1f}", rank["saves_rank"]),
        ("Penalty saves", int(stat["pens_saved"]), rank["saved_pens_rank"]),
        ("Clean sheets", int(stat["clean_sheets"]), rank["cs_rank"]),
    ]
else:
    cards = [
        ("Points", int(stat["points"]), rank["points_rank"]),
        ("Form", form, rank["form_rank"]),
        ("Goals", int(stat["goals"]), rank["goals_rank"]),
        ("Assists", int(stat["assists"]), rank["assists_rank"]),
        ("Def. actions / 90", f"{defcons_p90:.1f}", rank["dcp90_rank"]),
        ("Clean sheets", int(stat["clean_sheets"]), rank["cs_rank"]),
    ]
metric_row(cards, rank_hint=f"Rank among {position.lower()}s")

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

st.html(section_header_html("Performance"))

pf = {column: int(stat[column]) for column in stat.index if column.startswith("pf_")}
fig_breakdown, _ = points_breakdown_chart(**pf)
fig_trend = gameweek_trend(get_gameweek_points(player_id, range_label), team_colour)
fig_radar = player_radar(
    position,
    int(stat["points"]), int(best_row.get("max_points", 0)),
    int(stat["goals"]), int(best_row.get("max_goals", 0)),
    int(stat["assists"]), int(best_row.get("max_assists", 0)),
    int(stat["bonus"]), int(best_row.get("max_bonus", 0)),
    defcons_p90, float(best_row.get("max_dcp90", 0)),
    int(stat["clean_sheets"]), float(best_row.get("max_cs", 0)),
    int(stat["saves"]), float(best_row.get("max_saves", 0)),
    int(stat["pens_saved"]), float(best_row.get("max_pens_saved", 0)),
    player_name,
    team_colour,
)  # fmt: skip

left, right = st.columns(2, gap="medium")
with left, card("player-1"):
    st.html(card_title_html("Where the points come from", "Fantasy points by scoring category"))
    st.plotly_chart(fig_breakdown, width="stretch", theme=None, key="points_breakdown")
with right, card("player-2"):
    st.html(card_title_html("Points by gameweek"))
    st.plotly_chart(fig_trend, width="stretch", theme=None, key="gameweek_trend")

left, right = st.columns(2, gap="medium")
with left, card("player-3"):
    st.html(card_title_html("Player profile", f"Each axis as a % of the best {position.lower()}"))
    st.plotly_chart(fig_radar, width="stretch", theme=None, key="player_radar")
with right, card("player-4"):
    st.html(card_title_html("Minutes played", "Share of the minutes available"))
    st.html(minutes_meter_html(minutes, int(stat["minutes_not_played"])))

with card("player-5"):
    st.html(
        card_title_html(
            "Actual vs expected",
            "Output next to the underlying expected numbers. Consistently beating them suggests "
            "clinical finishing rather than luck.",
        )
    )
    st.plotly_chart(
        expected_vs_actual_chart(
            stat["goals"], stat["xg"], stat["assists"], stat["xa"], stat["goals_conceded"], stat["xga"], position
        ),
        width="stretch",
        theme=None,
        key="expected_vs_actual",
    )

st.html(section_header_html("Upcoming fixtures", "Next five gameweeks, coloured by FPL difficulty."))
with card("player-6"):
    fixture_card(get_next_5(player_id))
