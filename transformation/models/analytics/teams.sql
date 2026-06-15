{{ config(materialized='table') }}

select
    team_id                              as team_id,
    team_name                            as team_name,
    short_name                           as team_short_name,
    position                             as team_table_position,
    strength                             as team_strength
from {{ ref('stg_teams') }} p
inner join {{ source('analytics', 'seasons') }} s
    on p.season = s.id
where cast(getdate() as date)
      between s.start_date and s.end_date;