-- One row per fixture in the current season.
select
    p.id                 as fixture_id,
    p.event              as gameweek,
    p.team_a             as away_team,
    p.team_h             as home_team,
    p.team_a_score       as away_score,
    p.team_h_score       as home_score,
    p.team_h_difficulty  as home_difficulty,
    p.team_a_difficulty  as away_difficulty,
    p.finished           as finished,
    s.id                 as season
from {{ source('raw', 'raw_fixtures') }} p
{{ join_current_season('p') }}
