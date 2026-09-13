"""Query layer for player identity/profile info and upcoming fixtures.

Note: queries here build SQL via f-strings rather than bound
parameters. `selected_player` only ever comes from a Streamlit
selectbox populated from a trusted, known list of names (see
get_players below and Player.py), so this isn't exploitable today --
flagged in the improvement suggestions as worth tightening regardless.
"""
import pandas as pd
import streamlit as st

from database import run_query


@st.cache_data(ttl=600)
def get_players() -> pd.DataFrame:
    """All player IDs and full names, for the Player page's selectbox."""
    query = """
    select
        p_id,
        p_full_name
    from analytics.players
    order by p_team
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_player_info(selected_player: str) -> pd.DataFrame:
    """Identity, team colours/badge, and latest news for one player."""
    query = f"""
    select
        p_full_name,
        team_name       as team,
        pos_name        as position,
        p_price         as price,
        p_form          as form,
        p_creativity    as creativity,
        p_threat        as threat,
        p_influence     as influence,
        p_news          as news,
        p_news_date     as news_date,
        tm_primary      as 'primary',
        tm_secondary    as 'secondary',
        tm_image        as 'image'
    from analytics.players
    left join analytics.teams on team_id = p_team
    left join analytics.team_misc on tm_id = team_id
    left join analytics.positions on pos_id = p_position
    where p_full_name = '{selected_player}'
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_next_5(selected_player: str) -> pd.DataFrame:
    """The next 5 upcoming fixtures for `selected_player`'s team."""
    query = f"""
    select
        gw_id as gw,
        case when p_team = f_home_team then 'H' else 'A' end as venue,
        team_short_name as opponent,
        case when p_team = f_home_team then f_home_diff else f_away_diff end as difficulty
    from analytics.gameweeks
    left join analytics.fixtures on f_gameweek = gw_id
    left join analytics.players
        on p_team = f_home_team
        or p_team = f_away_team
    left join analytics.teams
        on team_id = case
            when p_team = f_home_team then f_away_team
            else f_home_team
        end
    where gw_deadline_time > '2026-04-19'
      and p_full_name = '{selected_player}'
    order by gw
    """
    return run_query(query)
