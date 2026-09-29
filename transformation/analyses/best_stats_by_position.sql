-- Best season totals among regular starters (5+ starts) in one position --
-- a sense-check for the "best in position" figures the dashboard's player
-- radar is scaled against. Compile with:
--     dbt compile -s best_stats_by_position --vars '{position: Defender}'
-- then run the SQL from target/compiled/.
with player_totals as (
    select
        ps.pg_id,
        sum(ps.pg_points)                                   as points,
        sum(ps.pg_minutes)                                  as minutes,
        sum(ps.pg_bonus)                                    as bonus,
        sum(ps.pg_defcons) * 90.0 / nullif(sum(ps.pg_minutes), 0) as dcp90,
        sum(ps.pg_points) * 90.0 / nullif(sum(ps.pg_minutes), 0)  as pp90,
        sum(ps.pg_starts)                                   as starts
    from {{ ref('player_stats') }} ps
    inner join {{ ref('players') }} p on p.p_id = ps.pg_id
    where p.p_position_name = '{{ var("position", "Midfielder") }}'
    group by ps.pg_id
    having sum(ps.pg_starts) >= 5
)

select
    max(points)                                  as max_points,
    max(minutes)                                 as max_minutes,
    max(bonus)                                   as max_bonus,
    cast(round(max(pp90), 1) as decimal(10, 1))  as max_pp90,
    cast(round(max(dcp90), 1) as decimal(10, 1)) as max_dcp90
from player_totals
