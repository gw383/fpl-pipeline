{{ config(materialized='view') }}

-- One row per Premier League team in the current season.
select
    p.id        as team_id,
    name        as team_name,
    position    as position,
    short_name  as short_name,
    strength    as strength,
    s.id        as season
from {{ source('raw', 'raw_teams') }} p
inner join {{ ref('seasons') }} s
    on p.season = s.display_name
where cast(getdate() as date) between s.start_date and s.end_date
