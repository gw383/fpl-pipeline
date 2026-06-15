{{ config(materialized='table') }}

select
    p.id                                               as gw_id,
    name                                               as gw_name,
    cast(deadline_time as datetime)                    as gw_deadline_time,
    max(p.id) over(partition by p.season) - p.id       as gw_offset
from {{ source('raw', 'raw_gameweeks') }} p
inner join {{ source('analytics', 'seasons') }} s
    on p.season = s.display_name
where cast(getdate() as date)
      between s.start_date and s.end_date;