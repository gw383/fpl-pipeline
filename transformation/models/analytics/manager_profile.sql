-- Dimension: one row per FPL manager in the warehouse (prefix m_).

-- Materialised as a view (not a table like the rest of analytics) so a
-- manager the dashboard loads on demand appears as soon as their raw rows
-- are written, without waiting for the next dbt run.
{{ config(materialized='view') }}

select
    entry_id       as m_id,
    player_name    as m_player_name,
    team_name      as m_team_name,
    overall_points as m_overall_points,
    overall_rank   as m_overall_rank,
    squad_value    as m_squad_value,
    bank           as m_bank,
    loaded_at      as m_loaded_at
from {{ ref('stg_manager_profiles') }}
