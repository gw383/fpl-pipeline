"""Home page: top-rated players, a metric-driven Best XI on a pitch
graphic, a fixture-difficulty grid, and the latest player news.
"""
import base64

import streamlit as st

from colours import DIFFICULTY_COLOURS
from components.differential_card import differential_card
from components.news import news_card
from components.rating_breakdown import rating_breakdown_html
from components.star_card import star_card
from components.team_fixtures import fixture_grid_header_html, team_fixture_card
from queries.player_stats import get_in_form_differentials, get_star_top5_by_position
from queries.team_data import get_best_11, get_latest_news, get_team_fixtures
from theme import TEXT_MUTED, inject_base_css, masthead_html, section_header_html

PITCH_IMAGE_PATH = "images/pitch.jpg"

# Selectbox label -> underlying metric_value column used by get_best_11.
BEST_11_METRICS = {
    "Points": "points",
    "Goals": "goals",
    "Assists": "assists",
    "xG": "xg",
    "Defcons": "defcons",
}

st.set_page_config(page_title="FPL Analytics", page_icon="⚽", layout="wide")
st.markdown(inject_base_css(), unsafe_allow_html=True)

with open(PITCH_IMAGE_PATH, "rb") as image_file:
    pitch_base64 = base64.b64encode(image_file.read()).decode()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.html(masthead_html("Data-driven picks for the week ahead"))

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

fixtures = get_team_fixtures()
news = get_latest_news()

if fixtures.empty:
    # Either the database couldn't be reached (database.run_query already
    # showed an error banner above) or analytics.fixtures genuinely has no
    # upcoming fixtures loaded yet. Either way there's nothing to build the
    # rest of this page from, so stop here rather than crashing on the
    # groupby/indexing below.
    st.warning("No fixture data is available right now.")
    st.stop()

if not news.empty:
    news["date"] = news["date"].dt.strftime("%d %b %H:%M")

# Order teams by average fixture difficulty over their next 5 gameweeks.
next_5_gws = fixtures["gw"].drop_duplicates().sort_values().head(5).tolist()

team_order = (
    fixtures[fixtures["gw"].isin(next_5_gws)]
    .groupby("team_name")["difficulty"]
    .mean()
    .sort_values()
    .index
    .tolist()
)

recommendations = get_star_top5_by_position()
differentials = get_in_form_differentials()

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

c2, c3, c4 = st.columns([1.75, 1.25, 1], gap="medium")

# -----------------------------------------------------------------
# Best XI
# -----------------------------------------------------------------

with c2, st.container(border=True):
    metric_label = st.selectbox("Build team based on", list(BEST_11_METRICS))
    selected_metric = BEST_11_METRICS[metric_label]

    best_11 = get_best_11(selected_metric)

    st.subheader(f"Best XI — {metric_label}")

    if best_11.empty:
        st.info("No player data available to build a team from yet.")
        goalkeeper = defenders = midfielders = forwards = best_11
    else:
        formation = best_11["formation"].iloc[0]

        goalkeeper = best_11[best_11["p_position"] == 1]
        defenders = best_11[best_11["p_position"] == 2]
        midfielders = best_11[best_11["p_position"] == 3]
        forwards = best_11[best_11["p_position"] == 4]

    def player_card(row) -> str:
        return f"""
        <div style="
            text-align:center;
            width:80px;
        ">

            <div style="
                background:#ffffff;
                border-radius:6px;
                padding:5px 4px;
                box-shadow:0 1px 3px rgba(0,0,0,0.18);
                font-size:11px;
                font-weight:700;
                line-height:13px;
                color:#0b0b0b;
            ">
                {row['player']}
            </div>

            <div style="
                display:inline-block;
                background:rgba(11,11,11,0.55);
                border-radius:999px;
                padding:2px 8px;
                font-size:10px;
                font-weight:700;
                color:white;
                margin-top:4px;
            ">
                {row['metric_value']:.2f}
            </div>

        </div>
        """

    # Four equal grid rows (one per position band) rather than the
    # previous flex column + manual transform:translateY nudges per
    # row -- those nudges were tuned for one particular formation and
    # could push adjacent rows into each other for others (a back-5
    # formation, or GKP nudged down 20px with not much headroom in a
    # fixed 540px pitch). A grid divides the height exactly four ways
    # with no per-row offset to get wrong, whatever the formation.
    st.html(
        f"""
        <div style="
            width:100%;
            height:540px;
            margin-top:5px;
            border-radius:12px;
            padding:20px 8px;
            box-sizing:border-box;

            background-image:linear-gradient(rgba(0,0,0,0.05), rgba(0,0,0,0.05)), url('data:image/jpeg;base64,{pitch_base64}');
            background-size:100% 100%;
            background-position:center;
            background-repeat:no-repeat;

            display:grid;
            grid-template-rows:repeat(4, 1fr);
        ">

            <!-- Goalkeeper -->
            <div style="display:flex;justify-content:space-evenly;align-items:center;min-width:0;">
                {''.join(player_card(row) for _, row in goalkeeper.iterrows())}
            </div>

            <!-- Defenders -->
            <div style="display:flex;justify-content:space-evenly;align-items:center;min-width:0;">
                {''.join(player_card(row) for _, row in defenders.iterrows())}
            </div>

            <!-- Midfielders -->
            <div style="display:flex;justify-content:space-evenly;align-items:center;min-width:0;">
                {''.join(player_card(row) for _, row in midfielders.iterrows())}
            </div>

            <!-- Forwards -->
            <div style="display:flex;justify-content:space-evenly;align-items:center;min-width:0;">
                {''.join(player_card(row) for _, row in forwards.iterrows())}
            </div>

        </div>
        """
    )

# -----------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------

with c3, st.container(border=True):
    st.subheader("Fixture Difficulty")
    st.caption("Teams ordered by their average difficulty over the next 5 gameweeks -- easiest run first.")

    # A heatmap needs a key: a small "easy -> hard" legend for the same
    # 5-step colour scale every cell below is drawn from.
    legend_swatches = "".join(
        f"""
        <div style="display:flex;align-items:center;gap:4px;">
            <span style="
                width:10px;height:10px;border-radius:3px;
                background:{colour};display:inline-block;
            "></span>
        </div>
        """
        for colour in DIFFICULTY_COLOURS.values()
    )
    st.html(
        f"""
        <div style="
            display:flex;
            align-items:center;
            gap:6px;
            font-size:11px;
            color:{TEXT_MUTED};
            font-weight:600;
            margin-bottom:10px;
        ">
            Easy
            <div style="display:flex;gap:3px;">{legend_swatches}</div>
            Hard
        </div>
        """
    )

    st.html(fixture_grid_header_html(next_5_gws))

    for team in team_order:
        team_df = fixtures[fixtures["team_name"] == team]
        position = int(team_df["team_table_position"].iloc[0])
        team_df = team_df[team_df["gw"].isin(next_5_gws)]

        grouped_fixtures = {gw: group for gw, group in team_df.groupby("gw")}

        st.html(team_fixture_card(team, position, grouped_fixtures, next_5_gws))

# -----------------------------------------------------------------
# News
# -----------------------------------------------------------------

with c4, st.container(border=True):
    st.subheader("Latest News")

    if news.empty:
        st.caption("No news items right now.")
    else:
        for _, row in news.iterrows():
            st.html(news_card(row))

# -----------------------------------------------------------------
# Top rated players
# -----------------------------------------------------------------

st.markdown("---")
st.html(
    section_header_html(
        "Top rated players",
        "The best-looking players going forward on the star rating alone, top 5 per "
        "position -- price isn't a factor in this rating at all, and positions are "
        "ranked separately rather than mixed into one list (a goalkeeper and a "
        "forward aren't a fair comparison on the same list).",
    )
)

if recommendations.empty:
    st.caption("No ratings available right now.")
else:
    position_sections = [
        (1, "Goalkeepers"),
        (2, "Defenders"),
        (3, "Midfielders"),
        (4, "Forwards"),
    ]
    pos_cols = st.columns(len(position_sections), gap="small")

    for col, (position_id, label) in zip(pos_cols, position_sections):
        with col:
            st.html(
                f'<div style="font-size:12px;font-weight:700;letter-spacing:0.04em;'
                f'text-transform:uppercase;color:{TEXT_MUTED};margin-bottom:8px;">{label}</div>'
            )
            position_players = recommendations[recommendations["p_position"] == position_id]

            if position_players.empty:
                st.caption("No ratings available.")
            else:
                # Each card is rendered individually (rather than one
                # big joined HTML block, as before) so it can have its
                # own "Show breakdown" toggle right underneath it.
                for _, row in position_players.iterrows():
                    st.html(star_card(row))
                    state_key = f"star_expanded_{int(row['p_id'])}"
                    expanded = st.session_state.get(state_key, False)
                    if st.button(
                        "Hide breakdown ▴" if expanded else "Show breakdown ▾",
                        key=f"btn_{state_key}",
                        use_container_width=True,
                    ):
                        st.session_state[state_key] = not expanded
                        expanded = not expanded
                    if expanded:
                        st.html(rating_breakdown_html(row, star=float(row["rating"])))

# -----------------------------------------------------------------
# In-form differentials
# -----------------------------------------------------------------

st.markdown("---")
st.html(
    section_header_html(
        "In-form differentials",
        "Low-ownership players (10% or less) currently in good recent form -- "
        "worth a look if you're after a punt rather than a template pick.",
    )
)

if differentials.empty:
    st.caption("No differentials meet the criteria right now.")
else:
    # Round 7.1: the per-card "Show breakdown" toggle was removed here
    # (feedback: with up to 20 cards on screen at once, a breakdown panel
    # per card was a lot of visual noise for a section that's meant to
    # be a quick scan -- the "Top rated players" section above, with far
    # fewer cards, keeps its breakdown). A plain 4-across grid, no longer
    # needing extra room under each card for a toggle button/panel.
    diff_cols = st.columns(4, gap="small")
    for i, (_, row) in enumerate(differentials.iterrows()):
        with diff_cols[i % 4]:
            st.html(differential_card(row))
            st.html('<div style="height:10px;"></div>')
