{{ config(materialized='view') }}

select 
p.id                as team_id,
name                as team_name,
position            as position,
short_name          as short_name,
strength            as strength,
s.id         as season
from {{ source('raw', 'raw_teams') }} p
inner join {{ source('analytics', 'seasons') }} s
    on p.season = s.display_name;
