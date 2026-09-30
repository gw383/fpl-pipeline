"""Team view: league position, results over a gameweek range ranked against
every other team, a form guide, and each result with scorers, assisters and
underlying xG/xA/xGA."""

import streamlit as st

from components.banner import club_banner_html
from components.metric_card import metric_row
from components.team_result_card import team_result_card
from formatting import build_contributor_strings, ordinal
from queries.common import RANGE_OPTIONS
from queries.team_results import (
    get_team_contributors,
    get_team_profile,
    get_team_rank_metrics,
    get_team_results,
    get_teams,
)
from theme import RESULT_COLOURS, STATUS_WARNING, page_header_html, section_header_html

st.html(page_header_html("Teams", "Results, form and underlying numbers for every Premier League club."))

teams = get_teams()
if teams.empty:
    st.warning("No team data is available right now.")
    st.stop()

team_names = dict(zip(teams["team_id"], teams["team_name"], strict=False))
col1, col2 = st.columns([4, 1])
with col1:
    team_id = st.selectbox("Team", list(team_names), format_func=team_names.get)
with col2:
    range_label = st.selectbox("Range", list(RANGE_OPTIONS))

profile = get_team_profile(team_id)
if profile.empty:
    st.warning(f"No profile data available for {team_names[team_id]}.")
    st.stop()

profile_row = profile.iloc[0]
table_position = int(profile_row["team_table_position"])

st.html(
    club_banner_html(
        f"""
        <div class="fpl-banner-title" style="font-size:34px;font-weight:800;line-height:1.05;letter-spacing:-0.02em;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{profile_row["team_name"]}</div>
        <div class="fpl-banner-meta" style="margin-top:6px;font-size:17px;font-weight:500;opacity:0.9;">
            {table_position}{ordinal(table_position)} in the Premier League
        </div>
        """,
        profile_row["primary_colour"],
        profile_row["secondary_colour"],
        profile_row["badge_file"],
        size="medium",
    )
)

# ---------------------------------------------------------------------------
# Range snapshot, ranked against every other team
# ---------------------------------------------------------------------------

st.html(
    section_header_html("Snapshot", f"{range_label} · the pill shows the rank among all 20 teams over the same range.")
)

ranks = get_team_rank_metrics(team_id, range_label)
if ranks.empty:
    st.info(f"{profile_row['team_name']} haven't played any finished fixtures in this range yet.")
else:
    r = ranks.iloc[0]
    games = int(r["games_played"])
    cards = [
        ("Record (W-D-L)", f"{int(r['wins'])}-{int(r['draws'])}-{int(r['losses'])}", r["form_points_rank"]),
        ("Goals scored", int(r["goals_scored"]), r["goals_scored_rank"]),
        ("Goals conceded", int(r["goals_conceded"]), r["goals_conceded_rank"]),
        ("Clean sheets", int(r["clean_sheets"]), r["clean_sheets_rank"]),
        ("xG", f"{r['total_xg']:.1f}", r["xg_rank"]),
        ("xGA", f"{r['total_xga']:.1f}", r["xga_rank"]),
    ]
    metric_row(
        [(title, value, int(card_rank)) for title, value, card_rank in cards], rank_hint="Rank among all 20 teams"
    )
    st.caption(f"Based on {games} finished game{'s' if games != 1 else ''}.")

# ---------------------------------------------------------------------------
# Form guide and results
# ---------------------------------------------------------------------------

st.html(section_header_html("Results", "Form guide reads oldest to newest; match cards below are most recent first."))

results = get_team_results(team_id, range_label)
if results.empty:
    st.caption(f"No finished fixtures for {profile_row['team_name']} in this range yet.")
    st.stop()

form_chips = "".join(
    f"""
    <div style="width:26px;height:26px;border-radius:999px;
                background:{RESULT_COLOURS.get(row["result"], STATUS_WARNING)};
                color:white;font-size:12px;font-weight:800;
                display:flex;align-items:center;justify-content:center;flex-shrink:0;"
         title="GW{int(row["gw_id"])} vs {row["opponent"]}: {int(row["own_score"])}-{int(row["opp_score"])}">
        {row["result"]}
    </div>
    """
    for _, row in results.sort_values("gw_id", kind="stable").iterrows()
)
st.html(
    f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:16px;flex-wrap:wrap;">'
    f'<span style="font-size:12px;font-weight:700;letter-spacing:0.04em;color:#898781;margin-right:6px;">FORM</span>'
    f"{form_chips}</div>"
)

contributors = build_contributor_strings(get_team_contributors(team_id, range_label))
for _, row in results.iterrows():
    goalscorers, assisters = contributors.get(int(row["gw_id"]), ("", ""))
    st.html(team_result_card(row, goalscorers, assisters))
