-- One row per FPL manager in the warehouse (configured or looked up in the
-- dashboard). Each manager's rows are replaced on every refresh, so it only
-- ever holds the current season.
select
    entry_id       as entry_id,
    player_name    as player_name,
    team_name      as team_name,
    overall_points as overall_points,
    overall_rank   as overall_rank,
    value          as squad_value,
    bank           as bank,
    load_timestamp as loaded_at
from {{ source('raw', 'raw_manager_profiles') }}
