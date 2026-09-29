-- Dimension: one row per gameweek (prefix gw_). gw_offset is the number of
-- gameweeks remaining after this one.
select
    gameweek_id                                  as gw_id,
    gameweek_name                                as gw_name,
    deadline_time                                as gw_deadline_time,
    max(gameweek_id) over () - gameweek_id       as gw_offset
from {{ ref('stg_gameweeks') }}
