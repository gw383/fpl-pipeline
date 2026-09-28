{{ config(materialized='view') }}

-- One row per tracked manager, per gameweek, per squad player: which
-- player, their squad slot (1-11 starting XI, 12-15 bench, in sub-
-- priority order), captain/vice-captain flags, and points multiplier.
--
-- No season filter here either -- raw.raw_manager_picks is a whole-
-- table replace refetched fresh from the live API every run (see
-- extraction/manager_picks.py), so it only ever holds current-season
-- picks, the same reasoning as stg_manager_profiles above.
select
    entry_id         as entry_id,
    event_id         as gw_id,
    player_id        as player_id,
    position         as squad_position,
    is_captain       as is_captain,
    is_vice_captain  as is_vice_captain,
    multiplier       as multiplier
from {{ source('raw', 'raw_manager_picks') }}
