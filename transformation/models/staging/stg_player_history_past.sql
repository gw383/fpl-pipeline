-- One row per current player per previous Premier League season, from FPL's
-- element-summary `history_past` (loaded once a season). Totals for that
-- season; xG and xA include penalties.
select
    h.player_id                               as player_id,
    h.element_code                            as player_code,
    replace(h.season_name, '/', '-')          as history_season,
    cast(left(h.season_name, 4) as int)       as history_start_year,
    cast(left(s.display_name, 4) as int)      as current_start_year,
    h.minutes                                 as minutes,
    h.starts                                  as starts,
    h.goals_scored                            as goals,
    h.assists                                 as assists,
    h.clean_sheets                            as clean_sheets,
    h.goals_conceded                          as goals_conceded,
    h.penalties_missed                        as penalties_missed,
    h.yellow_cards                            as yellow_cards,
    h.saves                                   as saves,
    h.bonus                                   as bonus,
    h.bps                                     as bps,
    h.expected_goals                          as xg,
    h.expected_assists                        as xa,
    h.defensive_contribution                  as defensive_contribution,
    h.clearances_blocks_interceptions         as clearances_blocks_interceptions,
    h.recoveries                              as recoveries,
    h.tackles                                 as tackles,
    cast(h.start_cost as float) / 10          as start_price,
    cast(h.end_cost as float) / 10            as end_price,
    h.team_join_date                          as team_join_date,
    s.id                                      as season
from {{ source('raw', 'raw_player_history_past') }} h
{{ join_current_season('h') }}
