-- One row per goal in the current season, from the Premier League match
-- API. Player and team codes are Opta codes, matching FPL's `code` fields.
select
    g.match_id        as match_id,
    g.event_id        as matchweek,
    g.home_team_code  as home_team_code,
    g.away_team_code  as away_team_code,
    g.team_code       as team_code,
    g.player_code     as player_code,
    g.assist_code     as assist_code,
    g.goal_type       as goal_type,
    g.period          as period,
    g.minute          as minute
from {{ source('raw', 'raw_pl_goal_events') }} g
{{ join_current_season('g') }}
