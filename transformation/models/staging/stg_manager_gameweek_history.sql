-- One row per tracked manager per gameweek: points, rank, budget,
-- transfer activity and any chip played.
select
    entry_id              as entry_id,
    event_id              as gw_id,
    points                as gw_points,
    total_points          as total_points,
    overall_rank          as overall_rank,
    bank                  as bank,
    value                 as squad_value,
    event_transfers       as transfers_made,
    event_transfers_cost  as transfers_cost,
    points_on_bench       as points_on_bench,
    active_chip           as active_chip
from {{ source('raw', 'raw_manager_gameweek_history') }}
