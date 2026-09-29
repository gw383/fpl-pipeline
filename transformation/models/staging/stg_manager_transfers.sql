-- One row per transfer made by a tracked manager.
select
    entry_id     as entry_id,
    element_in   as player_in_id,
    element_out  as player_out_id,
    event        as gw_id,
    time         as transfer_time
from {{ source('raw', 'raw_manager_transfers') }}
