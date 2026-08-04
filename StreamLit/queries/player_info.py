import pandas as pd
from database import engine



def get_players():
    query = """
    select
        p_id,
        p_full_name
    from analytics.players
    order by p_team
    """

    return pd.read_sql(query, engine)

def get_player_info(selected_player):

    query = f"""
    select
        p_full_name,
        team_name as team,
        pos_name as position,
        p_price as price,
        p_form as form,
        p_creativity as creativity,
        p_threat as threat,
        p_influence as influence,
        p_news as news,
        p_news_date as news_date,
        tm_primary as 'primary',
        tm_secondary as 'secondary',
        tm_image as 'image'
    from analytics.players
    left join analytics.teams on team_id = p_team
    left join analytics.team_misc on tm_id = team_id
    left join analytics.positions on pos_id = p_position
    where p_full_name = '{selected_player}'
    """

    return pd.read_sql(query, engine)

def get_next_5(selected_player):

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
    on team_id =
        case
            when p_team = f_home_team then f_away_team
            else f_home_team
        end
where gw_deadline_time > '2026-04-19'
and p_full_name = '{selected_player}'
order by gw;
    """

    return pd.read_sql(query, engine)



