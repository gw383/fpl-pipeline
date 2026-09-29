-- One row per Premier League team in the current season.
select
    p.id          as team_id,
    p.name        as team_name,
    p.short_name  as short_name,
    p.code        as team_code,
    p.position    as position,
    p.strength    as strength,
    s.id          as season
from {{ source('raw', 'raw_teams') }} p
{{ join_current_season('p') }}
