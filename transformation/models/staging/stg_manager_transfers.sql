{{ config(materialized='view') }}

-- One row per transfer a tracked manager has ever made: which player
-- came in, which went out, which gameweek it counted for, and when it
-- was made.
--
-- No season filter -- raw.raw_manager_transfers is a whole-table
-- replace of the manager's full transfer history as the live API
-- currently reports it (see extraction/manager_transfers.py), same
-- reasoning as the other stg_manager_* models above.
select
    entry_id     as entry_id,
    element_in   as player_in_id,
    element_out  as player_out_id,
    event        as gw_id,
    time         as transfer_time
from {{ source('raw', 'raw_manager_transfers') }}
