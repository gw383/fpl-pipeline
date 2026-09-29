-- Penalty goals per player per season from the Premier League match API's
-- goal events, for every season loaded (the current one and the previous
-- seasons loaded for players' history), with how many matchweeks of that
-- season are loaded so incomplete seasons can be spotted.
with loaded as (
    select season, count(distinct event_id) as matchweeks_loaded
    from {{ source('raw', 'raw_pl_goal_events') }}
    group by season
),

penalties as (
    select season, player_code, count(*) as penalty_goals
    from {{ source('raw', 'raw_pl_goal_events') }}
    where goal_type = 'Penalty'
    group by season, player_code
)

select
    l.season                       as season_label,
    p.player_code                  as player_code,
    coalesce(p.penalty_goals, 0)   as penalty_goals,
    l.matchweeks_loaded            as matchweeks_loaded
from loaded l
left join penalties p on p.season = l.season
