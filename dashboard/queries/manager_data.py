"""My Team page data for FPL managers.

Managers saved by the last pipeline run are read from the dashboard's data
file like everything else. One looked up since then is only in the
warehouse so far, so each query here can also run there (``live=True``).
That is why these are written in SQL both SQLite and SQL Server accept.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from database import run_live_query, run_query, table_exists
from settings import CACHE_TTL_SECONDS


def _run(live: bool):
    return run_live_query if live else run_query


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_known_managers() -> pd.DataFrame:
    """Every manager in the data file, for the quick-pick list."""
    return run_query(
        """
        select m_id, m_team_name, m_player_name
        from analytics.manager_profile
        order by m_team_name
        """
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_manager_profile(entry_id: int, live: bool = False) -> pd.DataFrame:
    """Name, team name and season-to-date standing."""
    return _run(live)(
        """
        select m_id, m_player_name, m_team_name, m_overall_points,
               m_overall_rank, m_squad_value, m_bank, m_loaded_at
        from analytics.manager_profile
        where m_id = :entry_id
        """,
        {"entry_id": entry_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_manager_squad(entry_id: int, live: bool = False) -> pd.DataFrame:
    """The manager's latest 15-man squad in squad-slot order (1-11 starting,
    12-15 bench in substitution order), with each player's points in that
    gameweek so far and whether his team has kicked off yet (gw_fixtures /
    gw_kicked_off: his club's fixtures that gameweek, and how many have
    started)."""
    return _run(live)(
        """
        select ms.gw_id, ms.squad_position, ms.is_starting, ms.is_captain, ms.is_vice_captain,
               ms.multiplier, ms.p_id, ms.player, ms.web_name, ms.p_position, ms.team_short_name,
               pr.star, pr.xpts_next_gw, t.team_primary_colour, t.team_secondary_colour,
               ps.pg_points as gw_points, fx.fixtures as gw_fixtures, fx.kicked_off as gw_kicked_off
        from analytics.manager_squad ms
        left join analytics.teams t on t.team_id = ms.team_id
        left join analytics.player_rating pr on pr.p_id = ms.p_id
        left join analytics.player_stats ps on ps.pg_id = ms.p_id and ps.pg_gameweek = ms.gw_id
        left join (
            select team_id, gw, count(*) as fixtures, sum(kicked_off) as kicked_off
            from (
                select f_home_team as team_id, f_gameweek as gw,
                       case when f_home_score is not null then 1 else 0 end as kicked_off
                from analytics.fixtures
                union all
                select f_away_team, f_gameweek,
                       case when f_home_score is not null then 1 else 0 end
                from analytics.fixtures
            ) sides
            group by team_id, gw
        ) fx on fx.team_id = ms.team_id and fx.gw = ms.gw_id
        where ms.m_id = :entry_id
        order by ms.squad_position
        """,
        {"entry_id": entry_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_gameweek_expected(gw: int) -> pd.DataFrame:
    """What the projection model expected from every player in ``gw``
    (predicted before it; written by projections/run.py). Empty until the
    model has run with that table."""
    empty = pd.DataFrame({"p_id": pd.Series(dtype="int64"), "gw_xpts": pd.Series(dtype="float64")})
    if not table_exists("player_gameweek_expected"):
        return empty
    expected = run_query(
        "select p_id, xpts as gw_xpts from analytics.player_gameweek_expected where gw = :gw",
        {"gw": gw},
    )
    if expected.empty:
        return empty
    return expected.astype({"p_id": "int64", "gw_xpts": "float64"})


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_manager_gameweek_history(entry_id: int, live: bool = False) -> pd.DataFrame:
    """Per-gameweek points, rank, budget, transfers and chips, latest first."""
    return _run(live)(
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
def get_manager_transfers(entry_id: int, limit: int = 10, live: bool = False) -> pd.DataFrame:
    """The manager's most recent transfers, latest first."""
    transfers = _run(live)(
        """
        select gw_id, transfer_time, player_in, player_in_position,
               player_out, player_out_position
        from analytics.manager_transfers
        where m_id = :entry_id
        order by transfer_time desc
        """,
        {"entry_id": entry_id},
    )
    return transfers.head(limit)
