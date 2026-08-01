with player_totals as
(
    select
        pg_id,
        sum(pg_points) AS points,
        sum(pg_minutes) AS minutes,
        sum(pg_bonus) AS bonus,
        sum(pg_defcons) * 90.0 / SUM(pg_minutes) AS dcp90,
        sum(pg_points) * 90.0 / SUM(pg_minutes) AS pp90,
        sum(pg_starts) AS starts
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
    max(points) AS max_points,
    max(minutes) AS max_minutes,
    max(bonus) AS max_bonus,
    cast(round(max(pp90),1) as decimal(10,1)) as max_pp90,
    cast(round(max(dcp90),1) as decimal(10,1)) AS max_dcp90
from player_totals