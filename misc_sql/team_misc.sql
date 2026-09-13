-- Ad-hoc analysis: the best per-position season totals for a given
-- position, used as a sense-check against the max_* figures the
-- Streamlit "Player" page computes itself (see queries/player_stats.py
-- get_best_stats). Not part of the dbt build or the app -- exploratory.
with player_totals as (
    select
        pg_id,
        sum(pg_points)                              as points,
        sum(pg_minutes)                              as minutes,
        sum(pg_bonus)                                as bonus,
        sum(pg_defcons) * 90.0 / sum(pg_minutes)     as dcp90,
        sum(pg_points) * 90.0 / sum(pg_minutes)      as pp90,
        sum(pg_starts)                               as starts
    from analytics.player_stats
    left join analytics.players
        on pg_id = p_id
    left join analytics.positions
        on p_position = pos_id
    where pos_name = '{position}'
    group by pg_id
    having sum(pg_starts) >= 5
)

select
    max(points)                                     as max_points,
    max(minutes)                                    as max_minutes,
    max(bonus)                                       as max_bonus,
    cast(round(max(pp90), 1) as decimal(10, 1))      as max_pp90,
    cast(round(max(dcp90), 1) as decimal(10, 1))     as max_dcp90
from player_totals
