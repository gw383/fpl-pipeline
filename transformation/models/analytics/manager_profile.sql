{{ config(materialized='table') }}

-- Dimension table: one row per tracked FPL manager, prefixed m_ (same
-- per-entity-prefix convention as p_ for players, f_ for fixtures,
-- team_ for teams).
select
    entry_id       as m_id,
    player_name    as m_player_name,
    team_name      as m_team_name,
    overall_points as m_overall_points,
    overall_rank   as m_overall_rank,
    squad_value    as m_squad_value,
    bank           as m_bank
from {{ ref('stg_manager_profiles') }}
