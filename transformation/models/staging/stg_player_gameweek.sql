{{ config(materialized='view') }}

select
    p.id                                    as player_id,
    event_id                                as gameweek_id,
    [stats.minutes]                         as 'minutes',
    [stats.goals_scored]                    as 'goals_scored',
    [stats.assists]                         as 'assists',
    [stats.clean_sheets]                    as 'clean_sheets',
    [stats.goals_conceded]                  as 'goals_conceded',
    [stats.own_goals]                       as 'own_goals',
    [stats.penalties_saved]                 as 'penalties_saved',
    [stats.penalties_missed]                as 'penalties_missed',
    [stats.yellow_cards]                    as 'yellow_cards',
    [stats.red_cards]                       as 'red_cards',
    [stats.saves]                           as 'saves',
    [stats.bonus]                           as 'bonus_points',
    [stats.bps]                             as 'bps',
    cast([stats.influence] as float)                       as 'influence',
    cast([stats.creativity] as float)                      as 'creativity',
    cast([stats.threat] as float)                       as 'threat',
    cast([stats.ict_index] as float)                     as 'ict_index',
    [stats.clearances_blocks_interceptions] as 'cl_bl_ints',
    [stats.recoveries]                      as 'recoveries',
    [stats.tackles]                         as 'tackles',
    [stats.defensive_contribution]          as 'defcons',
    [stats.starts]                          as 'starts',
    cast([stats.expected_goals] as float)                 as 'xG',
    cast([stats.expected_assists] as float)              as 'xA',
    cast([stats.expected_goal_involvements] as float)     as 'XGI',
    cast([stats.expected_goals_conceded] as float)       as 'xGa',
    [stats.total_points]                    as 'points',
    [stats.in_dreamteam]                    as 'dream_team',
    [stats.played]                          as 'played',
    s.id as 'season'
from {{ source('raw', 'raw_event_live') }} p
inner join {{ source('analytics', 'seasons') }} s
    on p.season = s.display_name
where cast(getdate() as date)
      between s.start_date and s.end_date;
