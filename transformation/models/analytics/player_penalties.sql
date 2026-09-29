-- Fact: penalties taken per player per FPL gameweek (only rows with at
-- least one). FPL records missed penalties but not scored ones; scored ones
-- come from the Premier League match API's goal events. Each PL match is
-- mapped to its FPL fixture by the two teams' codes, so a rearranged match
-- lands in the gameweek FPL played it in.
--
-- Used by the projection model to take penalties out of open-play xG.
with penalty_goals as (
    select
        p.p_id,
        f.f_gameweek       as gw_id,
        count(*)           as penalty_goals
    from {{ ref('stg_pl_goal_events') }} g
    inner join {{ ref('teams') }} th on th.team_code = g.home_team_code
    inner join {{ ref('teams') }} ta on ta.team_code = g.away_team_code
    inner join {{ ref('fixtures') }} f
        on f.f_home_team = th.team_id
        and f.f_away_team = ta.team_id
        and f.f_finished = 1
    inner join {{ ref('players') }} p on p.p_code = g.player_code
    where g.goal_type = 'Penalty'
    group by p.p_id, f.f_gameweek
),

penalty_misses as (
    select
        pg_id               as p_id,
        pg_gameweek         as gw_id,
        sum(pg_pens_missed) as penalties_missed
    from {{ ref('player_stats') }}
    where pg_pens_missed > 0
    group by pg_id, pg_gameweek
)

select
    coalesce(g.p_id, m.p_id)                                    as p_id,
    coalesce(g.gw_id, m.gw_id)                                  as gw_id,
    coalesce(g.penalty_goals, 0)                                as penalty_goals,
    coalesce(m.penalties_missed, 0)                             as penalties_missed,
    coalesce(g.penalty_goals, 0) + coalesce(m.penalties_missed, 0) as penalties_taken
from penalty_goals g
full outer join penalty_misses m
    on m.p_id = g.p_id
    and m.gw_id = g.gw_id
