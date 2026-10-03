"""FPL Analytics dashboard -- entry point.

    cd dashboard
    streamlit run app.py

Sets up the site chrome (page config, styles, logo, top navigation and
footer) once, then runs whichever page in ``views/`` is selected.

Every page reads the dashboard's data file (see ``database.py``), so that
is loaded first: without it there is nothing to show.
"""

import streamlit as st

from database import DataUnavailable, current_data
from queries.team_data import get_gameweek_status
from settings import ICON, LOGO, PAGE_TITLE, REPO_URL
from theme import footer_html, inject_base_css

st.set_page_config(page_title=PAGE_TITLE, page_icon=str(ICON), layout="wide")
st.markdown(inject_base_css(), unsafe_allow_html=True)
st.logo(str(LOGO), size="large")

try:
    data = current_data()
except DataUnavailable as exc:
    st.error(f"The dashboard has no data to show yet. {exc}")
    st.stop()

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
notes = [f"Updated to gameweek {gameweek}"] if gameweek else []
if data.exported_at is not None:
    notes.append(f"data refreshed {data.exported_at:%d %b, %H:%M} UTC")
st.html(footer_html(REPO_URL, " &middot; ".join(notes)))
