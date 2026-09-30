"""My Team: any FPL manager's season so far, current squad on the pitch
(with captaincy and expected points), bench and recent transfers.

Enter a manager ID: if they're already in the warehouse they're shown
straight away; otherwise they're fetched from the FPL API, saved (and kept
up to date by the daily pipeline from then on), then shown.
"""

import pandas as pd
import streamlit as st

from components.card import card
from components.layout import side_by_side
from components.metric_card import metric_row
from components.pitch import gameweek_points_html, pitch_html, shirt_svg, squad_card, team_expected_points
from manager_loader import ManagerNotFound, load_manager, parse_manager_id
from queries.manager_data import (
    get_gameweek_expected,
    get_known_managers,
    get_manager_gameweek_history,
    get_manager_profile,
    get_manager_squad,
    get_manager_transfers,
)
from settings import MY_ENTRY_ID
from theme import (
    BORDER,
    PAGE_BG,
    POSITION_COLOURS,
    POSITION_LABELS,
    RADIUS_SM,
    STATUS_CRITICAL,
    STATUS_GOOD,
    TEXT_MUTED,
    TEXT_PRIMARY,
    card_title_html,
    page_header_html,
    section_header_html,
)

ID_HELP = (
    "The number in the address of your team's Points page on the FPL site: "
    "fantasy.premierleague.com/entry/<ID>/event/..."
)


def _int_or(value, default=None):
    return int(value) if pd.notna(value) else default


def _choose_saved_manager() -> None:
    if st.session_state.get("saved_manager") is not None:
        st.session_state["manager_id"] = int(st.session_state["saved_manager"])


# ---------------------------------------------------------------------------
# Manager lookup
# ---------------------------------------------------------------------------

if "manager_id" not in st.session_state:
    st.session_state["manager_id"] = parse_manager_id(st.query_params.get("manager")) or MY_ENTRY_ID

st.html(
    page_header_html(
        "My team",
        "Look up any FPL manager by ID. Managers who aren't saved yet are fetched from FPL, "
        "then kept up to date with the daily refresh.",
    )
)

known = get_known_managers()
lookup_col, saved_col = st.columns([2, 3], gap="large", vertical_alignment="bottom")
with lookup_col, side_by_side("manager-lookup"), st.form("manager_lookup", border=False):
    id_col, button_col = st.columns([3, 2], vertical_alignment="bottom")
    typed_id = id_col.text_input("FPL manager ID", value=str(st.session_state["manager_id"]), help=ID_HELP)
    submitted = button_col.form_submit_button("Show team", type="primary", width="stretch")

if submitted:
    parsed = parse_manager_id(typed_id)
    if parsed is None:
        st.error(f"'{typed_id}' isn't a valid FPL manager ID. It should be a whole number, like {MY_ENTRY_ID}.")
    else:
        st.session_state["manager_id"] = parsed
        st.session_state["saved_manager"] = None

if not known.empty:
    names = dict(zip(known["m_id"].astype(int), known["m_team_name"].fillna(known["m_id"].astype(str))))
    with saved_col:
        st.pills(
            "Saved managers",
            options=list(names),
            format_func=names.get,
            selection_mode="single",
            key="saved_manager",
            on_change=_choose_saved_manager,
        )

entry_id = int(st.session_state["manager_id"])
st.query_params["manager"] = str(entry_id)

# ---------------------------------------------------------------------------
# Fetch from FPL if this manager isn't in the warehouse yet
# ---------------------------------------------------------------------------

profile = get_manager_profile(entry_id)
if profile.empty:
    not_found = st.session_state.setdefault("managers_not_found", set())
    if entry_id in not_found:
        st.error(f"There's no FPL manager with ID {entry_id}. Check the number and try again.")
        st.stop()
    with st.status(f"Manager {entry_id} isn't saved yet, so fetching them from FPL...", expanded=False) as status:
        try:
            load_manager(entry_id)
        except ManagerNotFound:
            not_found.add(entry_id)
            status.update(label=f"No FPL manager with ID {entry_id}", state="error")
            st.stop()
        except Exception as exc:  # network/API/database problems: show, don't crash
            status.update(label=f"Couldn't fetch manager {entry_id} from FPL", state="error")
            st.error(f"Something went wrong fetching manager {entry_id}: {exc}")
            st.stop()
        status.update(label=f"Fetched and saved manager {entry_id}", state="complete")
    profile = get_manager_profile(entry_id)
    if profile.empty:
        st.warning(
            f"Manager {entry_id} was saved, but the warehouse isn't showing them yet. Run `dbt build` once so "
            "the manager models become views, and they'll appear straight away from then on."
        )
        st.stop()

profile_row = profile.iloc[0]
squad = get_manager_squad(entry_id)
history = get_manager_gameweek_history(entry_id)
latest = history.iloc[0] if not history.empty else pd.Series(dtype=object)
current_gw = int(squad["gw_id"].iloc[0]) if not squad.empty else None
if current_gw is not None:
    squad = squad.astype({"p_id": "int64"}).merge(get_gameweek_expected(current_gw), on="p_id", how="left")

active_chip = latest.get("active_chip") if not latest.empty and pd.notna(latest.get("active_chip")) else None
chip_note = f" · {active_chip} chip active" if active_chip else ""
manager_name = profile_row["m_player_name"]
byline = f"Managed by {manager_name}" if pd.notna(manager_name) and str(manager_name).strip() else "FPL squad"
gameweek_note = f" · Gameweek {current_gw}" if current_gw else ""

loaded_at = pd.to_datetime(profile_row.get("m_loaded_at"), utc=True, errors="coerce")
title_col, refresh_col = st.columns([4, 1], vertical_alignment="bottom")
with title_col:
    st.html(section_header_html(profile_row["m_team_name"], f"{byline}{gameweek_note}{chip_note}"))
with refresh_col:
    if st.button("Refresh from FPL", key="refresh_manager", width="stretch"):
        refreshed = False
        try:
            with st.spinner("Refreshing from FPL..."):
                load_manager(entry_id)
            refreshed = True
        except Exception as exc:  # keep showing the saved data
            st.error(f"Couldn't refresh from FPL: {exc}")
        if refreshed:
            st.rerun()
    if pd.notna(loaded_at):
        st.caption(f"Updated {loaded_at:%d %b, %H:%M} UTC")

if squad.empty:
    st.info(
        "FPL hasn't published a team for this manager yet. Squads appear once a gameweek deadline has "
        "passed, so check back after the next deadline."
    )
    st.stop()

overall_rank = _int_or(profile_row["m_overall_rank"])
gw_points = _int_or(latest.get("gw_points"))
transfers_made = _int_or(latest.get("transfers_made"), 0)
transfers_cost = _int_or(latest.get("transfers_cost"), 0)
expected_total = team_expected_points(squad)
metric_row(
    [
        ("Overall rank", f"{overall_rank:,}" if overall_rank else "-"),
        ("Overall points", _int_or(profile_row["m_overall_points"], 0)),
        (f"GW{current_gw} points", gw_points if gw_points is not None else "-"),
        (f"GW{current_gw} expected", f"{expected_total:.1f}" if expected_total is not None else "-"),
        ("Team value", f"£{_int_or(profile_row['m_squad_value'], 0) / 10:.1f}m"),
        ("In the bank", f"£{_int_or(profile_row['m_bank'], 0) / 10:.1f}m"),
        (f"GW{current_gw} transfers", f"{transfers_made}" + (f" (-{transfers_cost})" if transfers_cost else "")),
    ]
)
st.html('<div style="height:18px;"></div>')

squad_col, transfers_col = st.columns([1.7, 1], gap="large")

# ---------------------------------------------------------------------------
# Squad: starting XI on the pitch, bench underneath
# ---------------------------------------------------------------------------

with squad_col, card("my_team-1"):
    st.html(
        card_title_html(
            f"GW{current_gw} team",
            "Captain marked C, vice-captain VC. Once a player's team has kicked off: his points (white) next to the "
            "points the model expected before the gameweek (dark); before that, just the expected points.",
        )
    )
    st.html(pitch_html(squad[squad["is_starting"] == 1], squad_card, height=520))

    bench = squad[squad["is_starting"] == 0].sort_values("squad_position")
    bench_cards = "".join(
        f"""
        <div class="fpl-bench-card" style="flex:1;min-width:0;background:{PAGE_BG};border:1px solid {BORDER};
                    border-radius:{RADIUS_SM};padding:10px;text-align:center;">
            {shirt_svg(row["team_primary_colour"], row["team_secondary_colour"], int(row["p_position"]) == 1, size=26)}
            <div class="fpl-bench-pos"
                 style="font-size:10.5px;font-weight:700;color:{POSITION_COLOURS.get(int(row["p_position"]), TEXT_MUTED)};">
                {POSITION_LABELS.get(int(row["p_position"]), "")}
                <span style="color:{TEXT_MUTED};">&middot; SUB {int(row["squad_position"]) - 11}</span>
            </div>
            <div class="fpl-bench-name" style="font-size:13px;font-weight:700;color:{TEXT_PRIMARY};margin-top:3px;
                        white-space:nowrap;
                        overflow:hidden;text-overflow:ellipsis;">
                {row["web_name"] if pd.notna(row["web_name"]) else row["player"]}
            </div>
            <div class="fpl-bench-team" style="font-size:11px;color:{TEXT_MUTED};">{row["team_short_name"]}</div>
            {gameweek_points_html(row)}
        </div>
        """
        for _, row in bench.iterrows()
    )
    st.html(
        f'<div style="font-size:12px;font-weight:700;letter-spacing:0.06em;color:{TEXT_MUTED};margin:14px 0 8px 0;">'
        f'BENCH</div><div class="fpl-bench" style="display:flex;gap:8px;">{bench_cards}</div>'
    )

# ---------------------------------------------------------------------------
# Recent transfers
# ---------------------------------------------------------------------------

with transfers_col, card("my_team-2"):
    st.html(card_title_html("Recent transfers"))
    transfers = get_manager_transfers(entry_id)
    if transfers.empty:
        st.caption("No transfers made yet.")
    rows = "".join(
        f"""
        <div style="display:flex;gap:12px;align-items:center;padding:10px 2px;border-bottom:1px solid {BORDER};">
            <div style="font-size:11px;font-weight:700;color:{TEXT_MUTED};width:38px;flex-shrink:0;">
                GW{int(row["gw_id"])}
            </div>
            <div style="min-width:0;font-size:13px;line-height:1.5;">
                <div style="color:{STATUS_GOOD};font-weight:700;white-space:nowrap;overflow:hidden;
                            text-overflow:ellipsis;">&#9650; {row["player_in"]}</div>
                <div style="color:{STATUS_CRITICAL};font-weight:600;white-space:nowrap;overflow:hidden;
                            text-overflow:ellipsis;">&#9660; {row["player_out"]}</div>
            </div>
        </div>
        """
        for _, row in transfers.iterrows()
    )
    st.html(rows)
