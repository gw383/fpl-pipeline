{{ config(materialized='table') }}

-- Dimension table: one row per Premier League team, prefixed team_.
select
    team_id           as team_id,
    team_name         as team_name,
    short_name        as team_short_name,
    position          as team_table_position,
    strength          as team_strength
from {{ ref('stg_teams') }} p
inner join {{ ref('seasons') }} s
    on p.season = s.id
where cast(getdate() as date) between s.start_date and s.end_date
