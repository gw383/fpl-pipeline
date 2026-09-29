"""My Team page data for FPL managers in the warehouse."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from database import run_query
from settings import CACHE_TTL_SECONDS


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_known_managers() -> pd.DataFrame:
    """Every manager already in the warehouse, for the quick-pick list."""
    return run_query(
        """
        select m_id, m_team_name, m_player_name
        from analytics.manager_profile
        order by m_team_name
        """
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_manager_profile(entry_id: int) -> pd.DataFrame:
    """Name, team name and season-to-date standing."""
    return run_query(
        """
        select m_id, m_player_name, m_team_name, m_overall_points,
               m_overall_rank, m_squad_value, m_bank, m_loaded_at
        from analytics.manager_profile
        where m_id = :entry_id
        """,
        {"entry_id": entry_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_manager_squad(entry_id: int) -> pd.DataFrame:
    """The manager's latest 15-man squad in squad-slot order (1-11 starting,
    12-15 bench in substitution order)."""
    return run_query(
        """
        select ms.gw_id, ms.squad_position, ms.is_starting, ms.is_captain, ms.is_vice_captain,
               ms.multiplier, ms.p_id, ms.player, ms.web_name, ms.p_position, ms.team_short_name,
               pr.star, pr.xpts_next_gw, t.team_primary_colour, t.team_secondary_colour
        from analytics.manager_squad ms
        left join analytics.teams t on t.team_id = ms.team_id
        left join analytics.player_rating pr on pr.p_id = ms.p_id
        where ms.m_id = :entry_id
        order by ms.squad_position
        """,
        {"entry_id": entry_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_manager_gameweek_history(entry_id: int) -> pd.DataFrame:
    """Per-gameweek points, rank, budget, transfers and chips, latest first."""
    return run_query(
        """
        select gw_id, gw_points, total_points, overall_rank, bank, squad_value,
               transfers_made, transfers_cost, points_on_bench, active_chip
        from analytics.manager_gameweek_history
        where m_id = :entry_id
        order by gw_id desc
        """,
        {"entry_id": entry_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_manager_transfers(entry_id: int, limit: int = 10) -> pd.DataFrame:
    """The manager's most recent transfers, latest first."""
    return run_query(
        """
        select top (:limit)
            gw_id, transfer_time, player_in, player_in_position,
            player_out, player_out_position
        from analytics.manager_transfers
        where m_id = :entry_id
        order by transfer_time desc
        """,
        {"entry_id": entry_id, "limit": limit},
    )
