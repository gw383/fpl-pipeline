{{ config(materialized='table') }}

-- One row per tracked manager per gameweek: points, running total,
-- overall rank, budget, transfer activity that gameweek, and any chip
-- played -- feeds the My Team page's headline stats (most recent
-- gameweek) and could equally back a rank/points trend chart later
-- (the same shape queries.player_stats.get_gwk already feeds
-- charts.gameweek_trend with, just at manager level instead of
-- player level).
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
