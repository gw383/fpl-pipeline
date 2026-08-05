import pandas as pd
from database import engine



def get_team_fixtures():
    query = """
with team_fixtures as
(
    select
        f_home_team as team_id,
        f_gameweek as gw,
        'H' as venue,
        team_short_name as opponent,
        f_home_diff as difficulty

    from analytics.fixtures

    left join analytics.teams
        on team_id = f_away_team


    union all


    select
        f_away_team as team_id,
        f_gameweek as gw,
        'A' as venue,
        team_short_name as opponent,
        f_away_diff as difficulty

    from analytics.fixtures

    left join analytics.teams
        on team_id = f_home_team
)


select
    tf.team_id,
    t.team_name,
    t.team_table_position,
    tf.gw,
    tf.venue,
    tf.opponent,
    tf.difficulty

from team_fixtures tf

left join analytics.teams t
    on tf.team_id = t.team_id

left join analytics.gameweeks gw
    on tf.gw = gw.gw_id

where gw.gw_deadline_time > '2026-04-19'

order by
    tf.team_id,
    tf.gw;
    """

    return pd.read_sql(query, engine)

def get_latest_news():

    query = """
select

    top (10)
       p_full_name as player,
       p_news as news,
       p_news_date as date
from analytics.players where p_news_date is not null and p_news <> ''
order by p_news_date desc
    """

    return pd.read_sql(query, engine)

