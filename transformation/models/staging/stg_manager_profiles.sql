{{ config(materialized='view') }}

-- One row per tracked FPL manager: identity, overall season standing,
-- and current budget (squad value + bank).
--
-- No season filter/join here, unlike stg_players/stg_teams/stg_fixtures
-- -- raw.raw_manager_profiles isn't season-partitioned at all (see
-- extraction/manager_profiles.py: it's a whole-table replace of
-- whatever the FPL API's live /entry/<id>/ endpoint returns right now
-- for each tracked manager), so it only ever holds current-season data
-- by construction.
select
    entry_id       as entry_id,
    player_name    as player_name,
    team_name      as team_name,
    overall_points as overall_points,
    overall_rank   as overall_rank,
    value          as squad_value,
    bank           as bank
from {{ source('raw', 'raw_manager_profiles') }}
