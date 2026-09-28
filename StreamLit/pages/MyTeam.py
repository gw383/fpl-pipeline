"""My Team page: the user's own FPL squad (entry 194625) -- profile
headline stats, the current starting XI on the same pitch graphic the
Home page's Best XI uses (plus, unlike that view, the bench), and
recent transfers/chip history.

Deliberately its own, fully self-contained page rather than a refactor
of Home.py to share its pitch-rendering code -- the same reasoning
pages/Compare.py already gives for not refactoring Player.py: Home.py
needed zero changes and carries zero risk of a regression from this
addition. The pitch HTML below is the same visual pattern as Home.py's
Best XI (same pitch.jpg background, same 4-row grid-by-position
layout), just re-implemented here for a squad of specific named
players rather than an algorithmically-picked XI, with captain/vice-
captain badges and a bench row Home.py's version has no need for.
"""
import base64

import pandas as pd
import streamlit as st

from components.metric_card import metric_card
from queries.manager_data import (
    get_manager_gameweek_history,
    get_manager_profile,
    get_manager_squad,
    get_manager_transfers,
)
from theme import (
    BORDER,
    POSITION_LABELS,
    RADIUS_SM,
    SHADOW_CARD,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    YELLOW,
    inject_base_css,
    masthead_html,
    section_header_html,
)

# The user's own FPL manager entry ID. This is a personal, single-
# subject page (there's no "pick a manager" dropdown, unlike every
# other page's selectbox) so it lives here as one clearly documented
# constant rather than scattered through query calls -- change this if
# a different tracked manager should ever be shown instead. See
# extraction/ingest.py's TRACKED_ENTRY_IDS, which must also list
# whichever ID this is set to, or nothing will have been ingested for
# them.
MY_ENTRY_ID = 194625

PITCH_IMAGE_PATH = "images/pitch.jpg"

st.set_page_config(page_title="FPL Analytics", page_icon="🎽", layout="wide")
st.markdown(inject_base_css(), unsafe_allow_html=True)

with open(PITCH_IMAGE_PATH, "rb") as image_file:
    pitch_base64 = base64.b64encode(image_file.read()).decode()

st.html(masthead_html("Your squad, at a glance"))

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

profile = get_manager_profile(MY_ENTRY_ID)
squad = get_manager_squad(MY_ENTRY_ID)
history = get_manager_gameweek_history(MY_ENTRY_ID)
transfers = get_manager_transfers(MY_ENTRY_ID, limit=10)

if profile.empty or squad.empty:
    # Either the database couldn't be reached (database.run_query
    # already showed an error banner above) or this manager ID hasn't
    # been ingested yet -- MY_ENTRY_ID needs to also be in
    # extraction/ingest.py's TRACKED_ENTRY_IDS and the pipeline needs
    # to have run at least once since.
    st.warning(
        f"No data available yet for manager {MY_ENTRY_ID}. Make sure this ID is in "
        "extraction/ingest.py's TRACKED_ENTRY_IDS and the pipeline has run."
    )
    st.stop()

profile_row = profile.iloc[0]
current_gw = int(squad.iloc[0]["gw_id"])

# ---------------------------------------------------------------------------
# Header banner
# ---------------------------------------------------------------------------

st.html(
    f"""
    <div style="
        background:{SURFACE};
        border:1px solid {BORDER};
        border-radius:14px;
        padding:20px 26px;
        margin-bottom:22px;
        box-shadow:{SHADOW_CARD};
    ">
        <div style="font-size:26px;font-weight:800;color:{TEXT_PRIMARY};">
            {profile_row['m_team_name']}
        </div>
        <div style="font-size:15px;color:{TEXT_MUTED};margin-top:2px;">
            {profile_row['m_player_name']} &middot; Gameweek {current_gw}
        </div>
    </div>
    """
)

# ---------------------------------------------------------------------------
# Headline stats
# ---------------------------------------------------------------------------
# None of these carry a rank badge (metric_card's `rank` is optional
# now specifically for this) -- there's no natural "vs how many other
# managers" comparison this app tracks; only 1-2 manager IDs are ever
# ingested (see TRACKED_ENTRY_IDS), so a rank among them would be
# meaningless.

latest_history = history.iloc[0] if not history.empty else pd.Series(dtype=object)

gw_points = int(latest_history.get("gw_points")) if pd.notna(latest_history.get("gw_points")) else None
transfers_made = int(latest_history.get("transfers_made")) if pd.notna(latest_history.get("transfers_made")) else 0
transfers_cost = int(latest_history.get("transfers_cost")) if pd.notna(latest_history.get("transfers_cost")) else 0
active_chip = latest_history.get("active_chip") if not latest_history.empty else None

squad_value = float(profile_row["m_squad_value"]) / 10 if pd.notna(profile_row["m_squad_value"]) else 0.0
bank = float(profile_row["m_bank"]) / 10 if pd.notna(profile_row["m_bank"]) else 0.0
overall_rank = profile_row["m_overall_rank"]
overall_rank_display = f"{int(overall_rank):,}" if pd.notna(overall_rank) else "-"

transfers_label = str(transfers_made)
if transfers_cost:
    transfers_label += f" (-{transfers_cost} pts)"

chip_label = active_chip if active_chip else "None"

m1, m2, m3, m4, m5, m6 = st.columns(6)
with m1:
    metric_card("Overall rank", overall_rank_display)
with m2:
    metric_card("Overall points", int(profile_row["m_overall_points"]))
with m3:
    metric_card(f"GW{current_gw} points", gw_points if gw_points is not None else "-")
with m4:
    metric_card("Team value", f"£{squad_value:.1f}m")
with m5:
    metric_card("In the bank", f"£{bank:.1f}m")
with m6:
    metric_card(f"GW{current_gw} transfers", transfers_label)

if chip_label != "None":
    st.caption(f"Chip active this gameweek: **{chip_label}**")

st.markdown("---")

# ---------------------------------------------------------------------------
# Pitch view: starting XI
# ---------------------------------------------------------------------------

st.html(section_header_html("Starting XI", f"Gameweek {current_gw} -- captain marked C, vice-captain VC."))

starting = squad[squad["is_starting"] == 1]
bench = squad[squad["is_starting"] == 0].sort_values("squad_position")


def squad_player_card(row) -> str:
    badge = ""
    if row["is_captain"]:
        badge = "C"
    elif row["is_vice_captain"]:
        badge = "VC"

    badge_html = ""
    if badge:
        multiplier_note = f" &times;{int(row['multiplier'])}" if row["multiplier"] and row["multiplier"] > 1 else ""
        badge_html = f"""
        <div style="
            position:absolute;
            top:-6px;
            right:-6px;
            background:{YELLOW};
            color:white;
            font-size:10px;
            font-weight:800;
            border-radius:999px;
            padding:2px 6px;
            box-shadow:0 1px 3px rgba(0,0,0,0.3);
        ">
            {badge}{multiplier_note}
        </div>
        """

    star = row.get("star")
    star_html = ""
    if pd.notna(star):
        star_html = f"""
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
            {float(star):.1f}
        </div>
        """

    name = row["web_name"] if pd.notna(row["web_name"]) else row["player"]

    return f"""
    <div style="text-align:center;width:84px;position:relative;">
        {badge_html}
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
            {name}
            <div style="font-size:9px;font-weight:600;color:#6b6b6b;margin-top:1px;">
                {row['team_short_name']}
            </div>
        </div>
        {star_html}
    </div>
    """


position_rows = [(pos_id, starting[starting["p_position"] == pos_id]) for pos_id in (1, 2, 3, 4)]

st.html(
    f"""
    <div style="
        width:100%;
        height:520px;
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
        {''.join(
            f'<div style="display:flex;justify-content:space-evenly;align-items:center;min-width:0;">'
            f'{"".join(squad_player_card(row) for _, row in group.iterrows())}'
            f'</div>'
            for _, group in position_rows
        )}
    </div>
    """
)

# ---------------------------------------------------------------------------
# Bench
# ---------------------------------------------------------------------------

st.html(section_header_html("Bench", "In substitution-priority order."))

bench_cols = st.columns(len(bench) if len(bench) else 1)
for col, (_, row) in zip(bench_cols, bench.iterrows()):
    with col:
        st.html(
            f"""
            <div style="
                background:{SURFACE};
                border:1px solid {BORDER};
                border-radius:{RADIUS_SM};
                padding:10px;
                text-align:center;
                box-shadow:{SHADOW_CARD};
            ">
                <div style="font-size:10px;font-weight:700;color:{TEXT_MUTED};">
                    {POSITION_LABELS.get(int(row['p_position']), '')} &middot; SUB {int(row['squad_position']) - 11}
                </div>
                <div style="font-size:13px;font-weight:700;color:{TEXT_PRIMARY};margin-top:2px;">
                    {row['web_name'] if pd.notna(row['web_name']) else row['player']}
                </div>
                <div style="font-size:11px;color:{TEXT_MUTED};">
                    {row['team_short_name']}
                </div>
            </div>
            """
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# Recent transfers
# ---------------------------------------------------------------------------

st.html(section_header_html("Recent transfers"))

if transfers.empty:
    st.caption("No transfers made yet.")
else:
    for _, row in transfers.iterrows():
        st.html(
            f"""
            <div style="
                display:flex;
                justify-content:space-between;
                align-items:center;
                background:{SURFACE};
                border:1px solid {BORDER};
                border-radius:{RADIUS_SM};
                padding:10px 16px;
                margin-bottom:6px;
                box-shadow:{SHADOW_CARD};
            ">
                <div style="font-size:13px;color:{TEXT_MUTED};font-weight:700;">
                    GW{int(row['gw_id'])}
                </div>
                <div style="font-size:13px;color:{TEXT_PRIMARY};">
                    <span style="color:#c0392f;font-weight:700;">&#8595; {row['player_out']}</span>
                    &nbsp;&rarr;&nbsp;
                    <span style="color:#0ca34a;font-weight:700;">&#8593; {row['player_in']}</span>
                </div>
            </div>
            """
        )
