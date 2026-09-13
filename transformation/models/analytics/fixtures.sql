{{ config(materialized='table') }}

-- Fact table: one row per fixture, prefixed f_ for easy joining.
select
    fixture_id        as f_id,
    gameweek          as f_gameweek,
    away_team         as f_away_team,
    home_team         as f_home_team,
    away_score        as f_away_score,
    home_score        as f_home_score,
    home_difficulty   as f_home_diff,
    away_difficulty   as f_away_diff,
    finished          as f_finished
from {{ ref('stg_fixtures') }} p
inner join {{ ref('seasons') }} s
    on p.season = s.id
where cast(getdate() as date) between s.start_date and s.end_date
