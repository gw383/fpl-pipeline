"""Home page: top-rated players, a metric-driven Best XI on a pitch
graphic, a fixture-difficulty grid, and the latest player news.
"""
import base64

import streamlit as st

from components.differential_card import differential_card
from components.news import news_card
from components.star_card import star_card
from components.team_fixtures import team_fixture_card
from queries.player_stats import get_in_form_differentials, get_star_top5_by_position
from queries.team_data import get_best_11, get_latest_news, get_team_fixtures

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

with open(PITCH_IMAGE_PATH, "rb") as image_file:
    pitch_base64 = base64.b64encode(image_file.read()).decode()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <h1 style='margin-bottom:0;'>FPL Analytics Dashboard</h1>
    <p style='font-size:20px;color:#888;margin-top:0;'>
    </p>
    """,
    unsafe_allow_html=True,
)

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

c2, c3, c4 = st.columns([1.75, 1.25, 1], gap="small")

# -----------------------------------------------------------------
# Best XI
# -----------------------------------------------------------------

with c2:
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
                box-shadow:0 1px 3px rgba(0,0,0,0.15);
                font-size:11px;
                font-weight:700;
                line-height:13px;
            ">
                {row['player']}
            </div>

            <div style="
                font-size:10px;
                font-weight:600;
                color:white;
                margin-top:3px;
            ">
                {row['metric_value']:.2f}
            </div>

        </div>
        """

    st.html(
        f"""
        <div style="
            width:100%;
            height:540px;
            margin-top:5px;
            border-radius:12px;
            padding:20px 8px;
            box-sizing:border-box;

            background-image:url('data:image/jpeg;base64,{pitch_base64}');
            background-size:100% 100%;
            background-position:center;
            background-repeat:no-repeat;

            display:flex;
            flex-direction:column;
            justify-content:space-between;
        ">

            <!-- Goalkeeper -->
            <div style="
                display:flex;
                justify-content:center;
                align-items:center;
                width:100%;
                transform:translateY(20px);
            ">
                {''.join(player_card(row) for _, row in goalkeeper.iterrows())}
            </div>

            <!-- Defenders -->
            <div style="
                display:flex;
                justify-content:space-around;
                align-items:center;
                width:100%;
                transform:translateY(-5px);
            ">
                {''.join(player_card(row) for _, row in defenders.iterrows())}
            </div>

            <!-- Midfielders -->
            <div style="
                display:flex;
                justify-content:space-around;
                align-items:center;
                width:100%;
                transform:translateY(-5px);
            ">
                {''.join(player_card(row) for _, row in midfielders.iterrows())}
            </div>

            <!-- Forwards -->
            <div style="
                display:flex;
                justify-content:space-around;
                align-items:center;
                width:100%;
                transform:translateY(-5px);
            ">
                {''.join(player_card(row) for _, row in forwards.iterrows())}
            </div>

        </div>
        """
    )

# -----------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------

with c3:
    st.subheader("Fixture Difficulty")

    gw_headers = "".join(
        f"""
        <div style="
            width:65px;
            text-align:center;
            font-size:11px;
        ">
            GW {gw}
        </div>
        """
        for gw in next_5_gws
    )

    st.html(
        f"""
        <div style="
            display:flex;
            align-items:center;
            font-weight:700;
            font-size:12px;
            margin-bottom:4px;
        ">

            <div style="width:65px;">
                Team
            </div>

            <div style="display:flex;">
                {gw_headers}
            </div>

        </div>
        """
    )

    for team in team_order:
        team_df = fixtures[fixtures["team_name"] == team]
        position = int(team_df["team_table_position"].iloc[0])
        team_df = team_df[team_df["gw"].isin(next_5_gws)]

        grouped_fixtures = {gw: group for gw, group in team_df.groupby("gw")}

        st.html(team_fixture_card(team, position, grouped_fixtures, next_5_gws))

# -----------------------------------------------------------------
# News
# -----------------------------------------------------------------

with c4:
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
st.subheader("Top rated players")
st.caption(
    "The best-looking players going forward on the star rating alone, top "
    "5 per position -- price isn't a factor in this rating at all, and "
    "positions are ranked separately rather than mixed into one list (a "
    "goalkeeper and a forward aren't a fair comparison on the same list)."
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
            st.markdown(f"**{label}**")
            position_players = recommendations[recommendations["p_position"] == position_id]

            if position_players.empty:
                st.caption("No ratings available.")
            else:
                cards_html = "".join(
                    star_card(row) for _, row in position_players.iterrows()
                )
                st.html(
                    f"""
                    <div style="
                        display:flex;
                        flex-direction:column;
                        gap:6px;
                    ">
                        {cards_html}
                    </div>
                    """
                )

# -----------------------------------------------------------------
# In-form differentials
# -----------------------------------------------------------------

st.markdown("---")
st.subheader("In-form differentials")
st.caption(
    "Low-ownership players (10% or less) currently in good recent form -- "
    "worth a look if you're after a punt rather than a template pick."
)

if differentials.empty:
    st.caption("No differentials meet the criteria right now.")
else:
    cards_html = "".join(
        differential_card(row) for _, row in differentials.iterrows()
    )
    st.html(
        f"""
        <div style="
            display:flex;
            flex-wrap:wrap;
            gap:10px;
        ">
            {cards_html}
        </div>
        """
    )
