"""Home: this week's Best XI, latest news, fixture difficulty for every team,
the top-rated players per position and in-form differentials."""

import streamlit as st

from best_xi import pick_best_xi
from components.card import card
from components.differential_card import differential_card
from components.layout import side_by_side, two_per_row
from components.news import news_card
from components.pitch import best_xi_card, pitch_html
from components.rating_list import rating_list
from components.team_fixtures import fixture_grid_header_html, fixture_grid_html, team_fixture_card
from queries.player_stats import get_in_form_differentials, get_top_rated
from queries.team_data import get_gameweek_status, get_latest_news, get_player_season_totals, get_team_fixtures
from theme import DIFFICULTY_COLOURS, TEXT_MUTED, card_title_html, page_header_html, section_header_html

# Best XI selector label -> column in get_player_season_totals().
BEST_XI_METRICS = {
    "Points": "points",
    "Goals": "goals",
    "Assists": "assists",
    "xG": "xg",
    "Def. actions": "defcons",
}
POSITION_SECTIONS = [(1, "Goalkeepers"), (2, "Defenders"), (3, "Midfielders"), (4, "Forwards")]

status = get_gameweek_status()
eyebrow = ""
if status["next_gw"] and status["next_deadline"] is not None:
    eyebrow = f"Gameweek {status['next_gw']} deadline · {status['next_deadline']:%a %d %b, %H:%M}"
elif status["current_gw"]:
    eyebrow = f"Gameweek {status['current_gw']}"

st.html(
    page_header_html(
        "Fantasy Premier League analytics",
        "Ratings, form and fixtures for every Premier League player, built from the official FPL data "
        "and refreshed daily.",
        eyebrow=eyebrow,
    )
)

fixtures = get_team_fixtures()
if fixtures.empty:
    st.warning("No fixture data is available right now.")
    st.stop()

# ---------------------------------------------------------------------------
# Best XI and latest news
# ---------------------------------------------------------------------------

best_xi_col, news_col = st.columns([1.7, 1], gap="large")

with best_xi_col, card("home-1"):
    with side_by_side("best-xi-header"):
        title_col, picker_col = st.columns([2, 1], vertical_alignment="center")
    with picker_col:
        metric_label = st.selectbox("Build team by", list(BEST_XI_METRICS), label_visibility="collapsed")
    formation, best_xi = pick_best_xi(get_player_season_totals(), BEST_XI_METRICS[metric_label])
    with title_col:
        st.html(card_title_html("Team of the season", f"Best {formation or ''} by {metric_label.lower()}"))
    if best_xi.empty:
        st.info("No player data available to build a team from yet.")
    st.html(pitch_html(best_xi, best_xi_card))

with news_col, card("home-2"):
    st.html(card_title_html("Latest news", "Injuries, suspensions and availability"))
    news = get_latest_news(limit=15)
    with st.container(height=548, border=False, key="news-feed"):
        if news.empty:
            st.caption("No news items right now.")
        for _, row in news.iterrows():
            st.html(news_card(row))

# ---------------------------------------------------------------------------
# Fixture difficulty
# ---------------------------------------------------------------------------

next_5_gws = sorted(fixtures["gw"].unique())[:5]
upcoming = fixtures[fixtures["gw"].isin(next_5_gws)]
team_order = upcoming.groupby("team_name")["difficulty"].mean().sort_values().index

st.html(
    section_header_html(
        "Fixture difficulty",
        "Every team's next five gameweeks, easiest run first, coloured by FPL's difficulty rating.",
    )
)
with card("home-3"):
    swatches = "".join(
        f'<span style="width:12px;height:12px;border-radius:3px;background:{colour};display:inline-block;"></span>'
        for colour in DIFFICULTY_COLOURS.values()
    )
    st.html(
        f'<div style="display:flex;justify-content:flex-end;align-items:center;gap:6px;font-size:11.5px;'
        f'color:{TEXT_MUTED};font-weight:600;margin-bottom:6px;">Easier <div style="display:flex;gap:3px;">'
        f"{swatches}</div> Harder</div>"
    )
    rows = [fixture_grid_header_html(next_5_gws)]
    for team_name in team_order:
        team_fixtures = upcoming[upcoming["team_name"] == team_name]
        first = team_fixtures.iloc[0]
        rows.append(
            team_fixture_card(
                team_name,
                int(first["team_table_position"]),
                dict(tuple(team_fixtures.groupby("gw"))),
                next_5_gws,
                first.get("team_badge_file"),
                first.get("team_short_name"),
            )
        )
    st.html(fixture_grid_html("".join(rows)))

# ---------------------------------------------------------------------------
# Top rated players
# ---------------------------------------------------------------------------

st.html(
    section_header_html(
        "Top rated players",
        "The most expected points over the next five gameweeks (price isn't part of it). "
        "Open a player to see how their rating is made up.",
    )
)
top_rated = get_top_rated(per_position=5)
if top_rated.empty:
    st.caption("No ratings available right now.")
else:
    with two_per_row("top-rated"):
        for col, (position_id, label) in zip(st.columns(4, gap="medium"), POSITION_SECTIONS):
            with col:
                rating_list(top_rated[top_rated["p_position"] == position_id], label, position_id)

# ---------------------------------------------------------------------------
# Differentials
# ---------------------------------------------------------------------------

st.html(
    section_header_html(
        "Differentials",
        "Owned by 10% of managers or fewer, expected to start, and projected to score well over the next "
        "five gameweeks. Worth a look if you're after a punt.",
    )
)
differentials = get_in_form_differentials(limit=12)
if differentials.empty:
    st.caption("No differentials meet the criteria right now.")
else:
    with two_per_row("differentials"):
        cols = st.columns(4, gap="small")
    for i, (_, row) in enumerate(differentials.iterrows()):
        with cols[i % 4]:
            st.html(differential_card(row))
