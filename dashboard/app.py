"""FPL Analytics dashboard -- entry point.

    cd dashboard
    streamlit run app.py

Sets up the site chrome (page config, styles, logo, top navigation and
footer) once, then runs whichever page in ``views/`` is selected.
"""

import streamlit as st

from queries.team_data import get_gameweek_status
from settings import ICON, LOGO, PAGE_TITLE, REPO_URL
from theme import footer_html, inject_base_css

st.set_page_config(page_title=PAGE_TITLE, page_icon=str(ICON), layout="wide")
st.markdown(inject_base_css(), unsafe_allow_html=True)
st.logo(str(LOGO), size="large")

navigation = st.navigation(
    [
        st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("views/player.py", title="Players", icon=":material/person:"),
        st.Page("views/compare.py", title="Compare", icon=":material/compare_arrows:"),
        st.Page("views/team.py", title="Teams", icon=":material/shield:"),
        st.Page("views/rankings.py", title="Rankings", icon=":material/leaderboard:"),
        st.Page("views/my_team.py", title="My Team", icon=":material/groups:"),
    ],
    position="top",
)
navigation.run()

gameweek = get_gameweek_status()["current_gw"]
st.html(footer_html(REPO_URL, f"Updated to gameweek {gameweek}" if gameweek else ""))
