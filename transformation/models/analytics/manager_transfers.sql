{{ config(materialized='table') }}

-- One row per transfer a tracked manager has ever made, with the
-- player names/positions resolved on both sides -- raw.raw_manager_
-- transfers only carries element ids (player_in_id/player_out_id), so
-- this is the one place that join happens rather than every consumer
-- redoing it.
select
    mt.entry_id         as m_id,
    mt.gw_id            as gw_id,
    mt.transfer_time    as transfer_time,
    p_in.p_full_name    as player_in,
    p_in.p_position     as player_in_position,
    p_out.p_full_name   as player_out,
    p_out.p_position    as player_out_position
from {{ ref('stg_manager_transfers') }} mt
left join {{ ref('players') }} p_in on p_in.p_id = mt.player_in_id
left join {{ ref('players') }} p_out on p_out.p_id = mt.player_out_id
