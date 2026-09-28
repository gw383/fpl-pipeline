{{ config(materialized='view') }}

-- One row per tracked manager, per gameweek: that gameweek's points,
-- running total, overall rank, budget snapshot, transfer activity, and
-- any chip played -- read straight off the same API response
-- stg_manager_picks' source table is built from (see
-- extraction/manager_picks.py's own note on why these two raw tables
-- come from one fetch rather than two).
--
-- No season filter, same reasoning as the other stg_manager_* models.
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
