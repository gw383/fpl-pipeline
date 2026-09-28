"""Query layer for the My Team page: one tracked manager's profile,
current squad, gameweek-by-gameweek history (points/rank/budget/chips),
and transfer history.

Note: like every other query file in this project, these build SQL via
f-strings rather than bound parameters. `entry_id` here never comes from
user input at all (see pages/MyTeam.py -- MY_ENTRY_ID is a module-level
constant, not a selectbox), so this is even less of a concern than the
other query files' own player-name/range-filter arguments.
"""
import pandas as pd
import streamlit as st

from database import run_query


@st.cache_data(ttl=600)
def get_manager_profile(entry_id: int) -> pd.DataFrame:
    """Identity and season-to-date standing for one tracked manager."""
    query = f"""
    select
        m_id,
        m_player_name,
        m_team_name,
        m_overall_points,
        m_overall_rank,
        m_squad_value,
        m_bank
    from analytics.manager_profile
    where m_id = {entry_id}
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_manager_squad(entry_id: int) -> pd.DataFrame:
    """One row per player in `entry_id`'s current 15-man squad (their
    most recently ingested gameweek), ordered by squad slot -- starting
    XI (1-11) first, bench (12-15) after, in sub-priority order.
    """
    query = f"""
    select
        gw_id,
        squad_position,
        is_starting,
        is_captain,
        is_vice_captain,
        multiplier,
        p_id,
        player,
        web_name,
        p_position,
        team_short_name,
        star
    from analytics.manager_squad
    where m_id = {entry_id}
    order by squad_position
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_manager_gameweek_history(entry_id: int, limit: int = 38) -> pd.DataFrame:
    """`entry_id`'s gameweek-by-gameweek history, most recent first --
    points, running total, overall rank, budget, transfer activity and
    any chip played. `limit` defaults to the whole season; the My Team
    page only reads the most recent row for its headline stats, but the
    full history is here for anyone who wants a season trend later.
    """
    query = f"""
    select top ({limit})
        gw_id,
        gw_points,
        total_points,
        overall_rank,
        bank,
        squad_value,
        transfers_made,
        transfers_cost,
        points_on_bench,
        active_chip
    from analytics.manager_gameweek_history
    where m_id = {entry_id}
    order by gw_id desc
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_manager_transfers(entry_id: int, limit: int = 10) -> pd.DataFrame:
    """`entry_id`'s `limit` most recent transfers, most recent first."""
    query = f"""
    select top ({limit})
        gw_id,
        transfer_time,
        player_in,
        player_in_position,
        player_out,
        player_out_position
    from analytics.manager_transfers
    where m_id = {entry_id}
    order by transfer_time desc
    """
    return run_query(query)
