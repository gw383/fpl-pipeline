-- One row per tracked manager, gameweek and squad player. squad_position
-- is FPL's squad slot (1-11 starting XI, 12-15 bench in substitution
-- order), not a football position.
select
    entry_id         as entry_id,
    event_id         as gw_id,
    player_id        as player_id,
    position         as squad_position,
    is_captain       as is_captain,
    is_vice_captain  as is_vice_captain,
    multiplier       as multiplier
from {{ source('raw', 'raw_manager_picks') }}
