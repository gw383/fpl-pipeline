-- Fact: one row per tracked manager per gameweek.

-- Materialised as a view (not a table like the rest of analytics) so a
-- manager the dashboard loads on demand appears as soon as their raw rows
-- are written, without waiting for the next dbt run.
{{ config(materialized='view') }}

select
    entry_id         as m_id,
    gw_id            as gw_id,
    gw_points        as gw_points,
    total_points     as total_points,
    overall_rank     as overall_rank,
    bank             as bank,
    squad_value      as squad_value,
    transfers_made   as transfers_made,
    transfers_cost   as transfers_cost,
    points_on_bench  as points_on_bench,
    active_chip      as active_chip
from {{ ref('stg_manager_gameweek_history') }}
