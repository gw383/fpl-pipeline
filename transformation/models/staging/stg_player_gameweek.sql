-- One row per player per gameweek: the live scoring stats from the
-- event/<gw>/live endpoint. A double gameweek is a single row whose stats
-- are the sum of both matches (the API has no per-match split).
select
    p.id                                              as player_id,
    p.event_id                                        as gameweek_id,
    p.[stats.minutes]                                 as minutes,
    p.[stats.goals_scored]                            as goals_scored,
    p.[stats.assists]                                 as assists,
    p.[stats.clean_sheets]                            as clean_sheets,
    p.[stats.goals_conceded]                          as goals_conceded,
    p.[stats.own_goals]                               as own_goals,
    p.[stats.penalties_saved]                         as penalties_saved,
    p.[stats.penalties_missed]                        as penalties_missed,
    p.[stats.yellow_cards]                            as yellow_cards,
    p.[stats.red_cards]                               as red_cards,
    p.[stats.saves]                                   as saves,
    p.[stats.bonus]                                   as bonus_points,
    p.[stats.bps]                                     as bps,
    cast(p.[stats.influence] as float)                as influence,
    cast(p.[stats.creativity] as float)               as creativity,
    cast(p.[stats.threat] as float)                   as threat,
    cast(p.[stats.ict_index] as float)                as ict_index,
    p.[stats.clearances_blocks_interceptions]         as cl_bl_ints,
    p.[stats.recoveries]                              as recoveries,
    p.[stats.tackles]                                 as tackles,
    p.[stats.defensive_contribution]                  as defcons,
    p.[stats.starts]                                  as starts,
    cast(p.[stats.expected_goals] as float)             as xG,
    cast(p.[stats.expected_assists] as float)           as xA,
    cast(p.[stats.expected_goal_involvements] as float) as XGI,
    cast(p.[stats.expected_goals_conceded] as float)    as xGa,
    p.[stats.total_points]                            as points,
    p.[stats.in_dreamteam]                            as dream_team,
    p.[stats.played]                                  as played,
    s.id                                              as season
from {{ source('raw', 'raw_event_live') }} p
{{ join_current_season('p') }}
