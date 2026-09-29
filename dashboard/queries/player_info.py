"""Player identity, profile and upcoming fixtures."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from database import run_query
from settings import CACHE_TTL_SECONDS


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_players() -> pd.DataFrame:
    """Every player's ID and full name, for player selectors."""
    return run_query(
        """
        select p_id, p_full_name
        from analytics.players
        order by p_team, p_full_name
        """
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_player_info(player_id: int) -> pd.DataFrame:
    """Name, team, position, price, form, latest news and club branding."""
    return run_query(
        """
        select
            p.p_full_name,
            t.team_name              as team,
            p.p_position_name        as position,
            p.p_price                as price,
            p.p_form                 as form,
            p.p_news                 as news,
            p.p_news_date            as news_date,
            t.team_primary_colour    as primary_colour,
            t.team_secondary_colour  as secondary_colour,
            t.team_badge_file        as badge_file
        from analytics.players p
        left join analytics.teams t on t.team_id = p.p_team
        where p.p_id = :player_id
        """,
        {"player_id": player_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_next_5(player_id: int) -> pd.DataFrame:
    """The player's team's fixtures over the next 5 gameweeks: one row per
    fixture, two for a double gameweek, and a row with no opponent for a
    blank gameweek."""
    return run_query(
        """
        with next5 as (
            select top (5) gw_id
            from analytics.gameweeks
            where gw_deadline_time > getdate()
            order by gw_id
        ),

        player_team as (
            select p_team as team_id
            from analytics.players
            where p_id = :player_id
        )

        select
            n.gw_id                                                          as gw,
            case when f.f_home_team = pt.team_id then 'H' else 'A' end       as venue,
            opp.team_short_name                                              as opponent,
            case when f.f_home_team = pt.team_id then f.f_home_diff
                 else f.f_away_diff end                                      as difficulty
        from next5 n
        cross join player_team pt
        left join analytics.fixtures f
            on f.f_gameweek = n.gw_id
            and pt.team_id in (f.f_home_team, f.f_away_team)
        left join analytics.teams opp
            on opp.team_id = case when f.f_home_team = pt.team_id
                                  then f.f_away_team else f.f_home_team end
        order by n.gw_id
        """,
        {"player_id": player_id},
    )
