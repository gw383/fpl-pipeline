-- One row per gameweek in the current season.
select
    p.id                                 as gameweek_id,
    p.name                               as gameweek_name,
    cast(p.deadline_time as datetime)    as deadline_time,
    p.finished                           as finished,
    p.data_checked                       as data_checked,
    s.id                                 as season
from {{ source('raw', 'raw_gameweeks') }} p
{{ join_current_season('p') }}
