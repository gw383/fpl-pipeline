{{ config(materialized='table') }}

-- Dimension table: one row per gameweek, plus gw_offset (gameweeks
-- remaining in the season) used to build "next 5 fixtures" views.
select
    p.id                                          as gw_id,
    name                                          as gw_name,
    cast(deadline_time as datetime)               as gw_deadline_time,
    max(p.id) over (partition by p.season) - p.id as gw_offset
from {{ source('raw', 'raw_gameweeks') }} p
inner join {{ ref('seasons') }} s
    on p.season = s.display_name
where cast(getdate() as date) between s.start_date and s.end_date
