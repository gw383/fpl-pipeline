-- Fact: one row per transfer, with player names/positions on both sides.

-- Materialised as a view (not a table like the rest of analytics) so a
-- manager the dashboard loads on demand appears as soon as their raw rows
-- are written, without waiting for the next dbt run.
{{ config(materialized='view') }}

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
