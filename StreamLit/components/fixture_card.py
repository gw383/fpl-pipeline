"""A player's next 5 fixtures, colour-coded by difficulty (used on the Player page)."""
import streamlit as st

from colours import DIFFICULTY_COLOURS


def fixture_card(fixtures_df) -> None:
    """Render one column per upcoming gameweek, each showing that
    gameweek's fixture(s) for the selected player's team.

    Handles blank gameweeks (no game), single fixtures, and double
    gameweeks (two fixtures) differently.
    """
    cols = st.columns(5)
    gameweeks = fixtures_df["gw"].unique()

    for col, gw in zip(cols, gameweeks):
        with col:
            games = fixtures_df[fixtures_df["gw"] == gw].to_dict("records")

            st.markdown(
                f"""
                <div style="
                    text-align:center;
                    font-weight:700;
                    margin-bottom:8px;
                ">
                    GW{gw}
                </div>
                """,
                unsafe_allow_html=True,
            )

            if len(games) == 0:
                st.markdown(
                    """
                    <div style="
                        background:#ececec;
                        height:90px;
                        border-radius:10px;
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        color:#777;
                        font-weight:600;
                    ">
                        Blank
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            elif len(games) == 1:
                fixture = games[0]
                st.markdown(
                    f"""
                    <div style="
                        background:{DIFFICULTY_COLOURS[fixture['difficulty']]};
                        height:90px;
                        border-radius:10px;
                        display:flex;
                        flex-direction:column;
                        align-items:center;
                        justify-content:center;
                        color:white;
                        font-weight:700;
                    ">
                        <span style="font-size:24px;">
                            {fixture['opponent']}
                        </span>
                        <span style="font-size:16px;">
                            {fixture['venue']}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            else:
                for fixture in games:
                    st.markdown(
                        f"""
                        <div style="
                            background:{DIFFICULTY_COLOURS[fixture['difficulty']]};
                            height:42px;
                            border-radius:10px;
                            display:flex;
                            align-items:center;
                            justify-content:space-between;
                            padding:0 12px;
                            color:white;
                            font-weight:700;
                            margin-bottom:6px;
                        ">
                            <span>{fixture['opponent']}</span>
                            <span>{fixture['venue']}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    st.markdown("</div>", unsafe_allow_html=True)
