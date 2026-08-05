import streamlit as st
from queries.team_data import (get_team_fixtures, get_latest_news)
from queries.player_stats import get_star_top20
from components.team_fixtures import team_fixture_card
from components.news import news_card


st.set_page_config(
    page_title="FPL Analytics",
    page_icon="⚽",
    layout="wide"
)


# ---------- Header ----------

st.markdown("""
<h1 style='margin-bottom:0;'>⚽ FPL Analytics Dashboard</h1>
<p style='font-size:20px;color:#888;margin-top:0;'>
</p>
""", unsafe_allow_html=True)


# ---------- Load Fixture Data ----------

fixtures = get_team_fixtures()

news = get_latest_news()

news["date"] = (
    news["date"]
    .dt.strftime("%d %b %H:%M")
)



# Order teams by average fixture difficulty

team_order = (
    fixtures
    .groupby("team_name")["difficulty"]
    .mean()
    .sort_values()
    .index
    .tolist()
)


# ---------- Main Layout ----------

# ---------- Main Layout ----------

recommendations = get_star_top20()


c1, c2, c3 = st.columns(
    [0.8, 1.5, 0.8],
    gap="small"
)
# -------------------------------
# Top Players
# -------------------------------

with c1:

    st.subheader("Top rated players")

    for _, player in recommendations.iterrows():

        st.html(
        f"""
        <div style="
            display:flex;
            align-items:center;
            background:white;
            border-radius:6px;
            padding:3px 6px;
            margin-bottom:2px;
            height:24px;
            width:230px;
            box-shadow:0 1px 2px rgba(0,0,0,0.08);
        ">

            <div style="
                width:165px;
                font-size:12px;
                font-weight:700;
                white-space:nowrap;
                overflow:hidden;
                text-overflow:ellipsis;
            ">
                {player['player']}
            </div>

            <div style="
                margin-left:auto;
                font-size:12px;
                font-weight:700;
                color:#333;
            ">
                {player['rating']:.2f}
            </div>

        </div>
        """
        )



# -------------------------------
# Fixtures
# -------------------------------

with c2:

    st.subheader("Fixture Difficulty")


    next_5_gws = (
        fixtures["gw"]
        .drop_duplicates()
        .sort_values()
        .head(5)
        .tolist()
    )


    gw_headers = ""

    for gw in next_5_gws:

        gw_headers += f"""
        <div style="
            width:65px;
            text-align:center;
            font-size:11px;
        ">
            GW {gw}
        </div>
        """


    st.html(
    f"""
    <div style="
        display:flex;
        align-items:center;
        font-weight:700;
        font-size:12px;
        margin-bottom:4px;
    ">

        <div style="
            width:65px;
        ">
            Team
        </div>

        <div style="
            display:flex;
        ">
            {gw_headers}
        </div>

    </div>
    """
    )


    for team in team_order:


        team_df = fixtures[
            fixtures["team_name"] == team
        ]


        position = int(
            team_df["team_table_position"].iloc[0]
        )


        team_df = team_df[
            team_df["gw"].isin(next_5_gws)
        ]


        grouped_fixtures = {
            gw: group
            for gw, group in team_df.groupby("gw")
        }


        st.html(
            team_fixture_card(
                team,
                position,
                grouped_fixtures,
                next_5_gws
            )
        )



# -------------------------------
# News
# -------------------------------

with c3:

    st.subheader("Latest News")


    for _, row in news.iterrows():

        st.html(
            news_card(row)
        )
