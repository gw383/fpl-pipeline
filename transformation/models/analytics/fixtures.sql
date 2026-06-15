{{ config(materialized='table') }}

select
    fixture_id                        as f_id,
    gameweek                    as f_gameweek,
    away_team                   as f_away_team,
    home_team                   as f_home_team,
    away_score                  as f_away_score,
    home_score                  as f_home_score,
    home_difficulty             as f_home_diff,
    away_difficulty             as f_away_diff
from {{ ref('stg_fixtures') }} p
inner join {{ source('analytics', 'seasons') }} s
    on p.season = s.id
where cast(getdate() as date)
      between s.start_date and s.end_date;