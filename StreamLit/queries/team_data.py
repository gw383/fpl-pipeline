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

where gw.gw_deadline_time > getdate()

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
    from analytics.players
    where p_news_date is not null
      and p_news <> ''
    order by p_news_date desc
    """

    news = pd.read_sql(query, engine)

    news["date"] = pd.to_datetime(news["date"])

    return news

def get_best_11(metric):

    query = f"""
declare @metric varchar(30) = '{metric}';

with player_metrics as
(
select
    p.p_id,
    p.p_full_name as player,
    p.p_position,

    case @metric
        when 'points'
            then sum(ps.pg_points)

        when 'goals'
            then sum(ps.pg_goals)

        when 'assists'
            then sum(ps.pg_assists)

        when 'xg'
            then sum(ps.pg_xG)

        when 'defcons'
            then sum(ps.pg_defcons)

        else 0
    end as metric_value

from analytics.players p
left join analytics.player_stats ps
    on p.p_id = ps.pg_id

group by
    p.p_id,
    p.p_full_name,
    p.p_position
),

ranked_players as
(
select
    *,
    row_number() over (
        partition by p_position
        order by metric_value desc
    ) as position_rank
from player_metrics
),

formations as
(
select '3-4-3' as formation, 3 as defenders, 4 as midfielders, 3 as forwards
union all
select '3-5-2', 3, 5, 2
union all
select '4-3-3', 4, 3, 3
union all
select '4-4-2', 4, 4, 2
union all
select '4-5-1', 4, 5, 1
union all
select '5-3-2', 5, 3, 2
union all
select '5-4-1', 5, 4, 1
),

formation_scores as
(
select
    f.formation,
    f.defenders,
    f.midfielders,
    f.forwards,
    coalesce(max(case
                when rp.p_position = 1
                and rp.position_rank <= 1
                then rp.metric_value
            end), 0)
    +
    coalesce(sum(case
                when rp.p_position = 2
                and rp.position_rank <= f.defenders
                then rp.metric_value
                else 0
            end), 0)
    +
    coalesce(sum(case
                when rp.p_position = 3
                and rp.position_rank <= f.midfielders
                then rp.metric_value
                else 0
            end), 0)
    +
    coalesce(sum(case
                when rp.p_position = 4
                and rp.position_rank <= f.forwards
                then rp.metric_value
                else 0
            end), 0) as formation_score

from formations f
cross join ranked_players rp
group by
    f.formation,
    f.defenders,
    f.midfielders,
    f.forwards
),

best_formation as
(
select top 1
    *
from formation_scores
order by formation_score desc
)

select
    bf.formation,
    rp.player,
    rp.p_position,
    rp.metric_value,
    p_team

from best_formation bf
join ranked_players rp
    on
        (rp.p_position = 1
        and rp.position_rank <= 1)

        or

        (rp.p_position = 2
        and rp.position_rank <= bf.defenders)

        or

        (rp.p_position = 3
        and rp.position_rank <= bf.midfielders)

        or

        (rp.p_position = 4
        and rp.position_rank <= bf.forwards)
left join analytics.players p on p.p_id = rp.p_id
order by
    rp.p_position,
    rp.position_rank;
    """

    return pd.read_sql(query, engine)

