"""Team page data: profile, results, goal contributors and league ranks."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from database import run_query
from queries.common import range_filter_sql
from settings import CACHE_TTL_SECONDS


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_teams() -> pd.DataFrame:
    """Every team's ID and name, for the team selector."""
    return run_query("select team_id, team_name from analytics.teams order by team_name")


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_team_profile(team_id: int) -> pd.DataFrame:
    """Name, league position and club branding for one team."""
    return run_query(
        """
        select
            team_name,
            team_short_name,
            team_table_position,
            team_primary_colour    as primary_colour,
            team_secondary_colour  as secondary_colour,
            team_badge_file        as badge_file
        from analytics.teams
        where team_id = :team_id
        """,
        {"team_id": team_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_team_results(team_id: int, range_label: str) -> pd.DataFrame:
    """The team's finished fixtures in the range, most recent first."""
    return run_query(
        f"""
        select
            r.gw_id,
            r.venue,
            opp.team_short_name as opponent,
            r.own_score,
            r.opp_score,
            r.result,
            r.team_xg,
            r.team_xa,
            r.team_xga,
            r.is_double_gw
        from analytics.team_fixture_results r
        left join analytics.teams opp on opp.team_id = r.opponent_id
        where r.team_id = :team_id
          and {range_filter_sql(range_label, "r.gw_id")}
        order by r.gw_id desc, r.venue
        """,
        {"team_id": team_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_team_contributors(team_id: int, range_label: str) -> pd.DataFrame:
    """Every goal scorer / assister for the team per gameweek in the range."""
    return run_query(
        f"""
        select
            ps.pg_gameweek as gw_id,
            p.p_full_name  as player,
            ps.pg_goals    as goals,
            ps.pg_assists  as assists
        from analytics.player_stats ps
        inner join analytics.players p on p.p_id = ps.pg_id
        where p.p_team = :team_id
          and (ps.pg_goals > 0 or ps.pg_assists > 0)
          and {range_filter_sql(range_label, "ps.pg_gameweek")}
        order by ps.pg_gameweek desc, ps.pg_goals desc, ps.pg_assists desc
        """,
        {"team_id": team_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_team_rank_metrics(team_id: int, range_label: str) -> pd.DataFrame:
    """The team's totals over the range and its rank against every other team
    (distinct ranks; league points use the standard 3/1/0)."""
    return run_query(
        f"""
        with team_totals as (
            select
                team_id,
                count(*)                                              as games_played,
                sum(case when result = 'W' then 1 else 0 end)         as wins,
                sum(case when result = 'D' then 1 else 0 end)         as draws,
                sum(case when result = 'L' then 1 else 0 end)         as losses,
                sum(own_score)                                        as goals_scored,
                sum(opp_score)                                        as goals_conceded,
                sum(case when opp_score = 0 then 1 else 0 end)        as clean_sheets,
                -- a double gameweek's xG is repeated on both of its fixtures
                sum(team_xg * 1.0 / fixtures_in_gw)                   as total_xg,
                sum(team_xa * 1.0 / fixtures_in_gw)                   as total_xa,
                sum(team_xga * 1.0 / fixtures_in_gw)                  as total_xga
            from analytics.team_fixture_results
            where {range_filter_sql(range_label, "gw_id")}
            group by team_id
        ),

        ranked as (
            select
                *,
                row_number() over (order by goals_scored desc)        as goals_scored_rank,
                row_number() over (order by goals_conceded asc)       as goals_conceded_rank,
                row_number() over (order by clean_sheets desc)        as clean_sheets_rank,
                row_number() over (order by total_xg desc)            as xg_rank,
                row_number() over (order by total_xga asc)            as xga_rank,
                row_number() over (order by wins * 3 + draws desc)    as form_points_rank
            from team_totals
        )

        select *
        from ranked
        where team_id = :team_id
        """,
        {"team_id": team_id},
    )
