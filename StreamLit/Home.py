import streamlit as st
import base64
from queries.team_data import (get_team_fixtures, get_latest_news, get_best_11)
from queries.player_stats import get_star_top20
from components.team_fixtures import team_fixture_card
from components.news import news_card



st.set_page_config(
    page_title="FPL Analytics",
    page_icon="⚽",
    layout="wide"
)


pitch_path = "images/pitch.jpg"

with open(pitch_path, "rb") as image_file:
    pitch_base64 = base64.b64encode(
        image_file.read()
    ).decode()

# ---------- Header ----------

st.markdown("""
<h1 style='margin-bottom:0;'>FPL Analytics Dashboard</h1>
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


c1, c2, c3, c4 = st.columns(
    [0.5, 1.75, 1.25, 1],
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



with c2:

    metric = st.selectbox(
        "Build team based on",
        [
            "Points",
            "Goals",
            "Assists",
            "xG",
            "Defcons"
        ]
    )

    metric_map = {
        "Points": "points",
        "Goals": "goals",
        "Assists": "assists",
        "xG": "xg",
        "Defcons": "defcons"
    }

    selected_metric = metric_map[metric]

    best_11 = get_best_11(selected_metric)
    
    st.subheader(f"Best XI — {metric}")

    formation = best_11["formation"].iloc[0]

    # Split players by position
    goalkeeper = best_11[best_11["p_position"] == 1]
    defenders = best_11[best_11["p_position"] == 2]
    midfielders = best_11[best_11["p_position"] == 3]
    forwards = best_11[best_11["p_position"] == 4]

    def player_card(row):

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

    # Pitch
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

# -------------------------------
# Fixtures
# -------------------------------

with c3:

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

with c4:

    st.subheader("Latest News")


    for _, row in news.iterrows():

        st.html(
            news_card(row)
        )
