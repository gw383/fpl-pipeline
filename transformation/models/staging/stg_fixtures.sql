{{ config(materialized='view') }}

select 
    p.id                        as fixture_id,
    event                       as gameweek,
    team_a                      as away_team,
    team_h                      as home_team,
    team_a_score                as away_score,
    team_h_score                as home_score,
    team_h_difficulty           as home_difficulty,
    team_a_difficulty           as away_difficulty,
    finished                    as finished,
    s.id                 as season
from {{ source('raw', 'raw_fixtures') }} p
inner join {{ source('analytics', 'seasons') }} s
    on p.season = s.display_name
where cast(getdate() as date)
      between s.start_date and s.end_date;