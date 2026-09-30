"""Home page data: fixture grid, latest news and season totals for the Best XI."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from database import run_query
from settings import CACHE_TTL_SECONDS


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_team_fixtures() -> pd.DataFrame:
    """Every team's upcoming fixtures (home and away) with FPL difficulty."""
    return run_query(
        """
        with team_fixtures as (
            select f_home_team as team_id, f_away_team as opponent_id, f_gameweek as gw,
                   'H' as venue, f_home_diff as difficulty
            from analytics.fixtures

            union all

            select f_away_team, f_home_team, f_gameweek, 'A', f_away_diff
            from analytics.fixtures
        )
        select
            tf.team_id,
            t.team_name,
            t.team_short_name,
            t.team_table_position,
            t.team_badge_file,
            tf.gw,
            tf.venue,
            opp.team_short_name as opponent,
            tf.difficulty
        from team_fixtures tf
        inner join analytics.teams t on t.team_id = tf.team_id
        left join analytics.teams opp on opp.team_id = tf.opponent_id
        inner join analytics.gameweeks gw on gw.gw_id = tf.gw
        where gw.gw_deadline_time > getdate()
        order by tf.team_id, tf.gw
        """
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_gameweek_status() -> dict:
    """The latest gameweek whose deadline has passed and the next deadline."""
    df = run_query(
        """
        select
            (select max(gw_id) from analytics.gameweeks where gw_deadline_time < getdate())  as current_gw,
            (select min(gw_id) from analytics.gameweeks where gw_deadline_time >= getdate()) as next_gw,
            (select min(gw_deadline_time) from analytics.gameweeks
              where gw_deadline_time >= getdate())                                           as next_deadline
        """
    )
    if df.empty:
        return {"current_gw": None, "next_gw": None, "next_deadline": None}
    row = df.iloc[0]
    return {
        "current_gw": int(row["current_gw"]) if pd.notna(row["current_gw"]) else None,
        "next_gw": int(row["next_gw"]) if pd.notna(row["next_gw"]) else None,
        "next_deadline": pd.to_datetime(row["next_deadline"]) if pd.notna(row["next_deadline"]) else None,
    }


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_latest_news(limit: int = 10) -> pd.DataFrame:
    """The most recent player news items."""
    news = run_query(
        """
        select top (:limit)
            p_full_name as player,
            p_news      as news,
            p_news_date as date
        from analytics.players
        where p_news_date is not null
          and p_news <> ''
        order by p_news_date desc
        """,
        {"limit": limit},
    )
    if not news.empty:
        news["date"] = pd.to_datetime(news["date"])
    return news


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_player_season_totals() -> pd.DataFrame:
    """Season totals per player for every Best XI metric, fetched once so
    switching metric doesn't need another query."""
    return run_query(
        """
        select
            p.p_id,
            p.p_full_name                  as player,
            p.p_web_name                   as web_name,
            p.p_position,
            t.team_short_name,
            t.team_primary_colour,
            t.team_secondary_colour,
            coalesce(sum(ps.pg_points), 0)  as points,
            coalesce(sum(ps.pg_goals), 0)   as goals,
            coalesce(sum(ps.pg_assists), 0) as assists,
            coalesce(sum(ps.pg_xG), 0)      as xg,
            coalesce(sum(ps.pg_defcons), 0) as defcons
        from analytics.players p
        left join analytics.teams t on t.team_id = p.p_team
        left join analytics.player_stats ps on ps.pg_id = p.p_id
        group by p.p_id, p.p_full_name, p.p_web_name, p.p_position,
                 t.team_short_name, t.team_primary_colour, t.team_secondary_colour
        """
    )
