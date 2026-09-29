-- Fact: each current player's previous Premier League seasons (prefix ps_),
-- from FPL's history_past, with the penalties he took that season (penalty
-- goals from the Premier League match API + FPL's missed penalties).
--
-- Used by the projection model as a prior on ability: last season's open-play
-- xG, xA, BPS and defensive actions per 90. ps_penalties_known is 0 when that
-- season's goal events aren't fully loaded, in which case the penalty count
-- only includes misses.
with seasons as (
    select distinct season_label, matchweeks_loaded
    from {{ ref('stg_pl_penalties_by_season') }}
)

select
    p.p_id                                              as p_id,
    h.history_season                                    as ps_season,
    h.current_start_year - h.history_start_year         as ps_seasons_ago,
    h.minutes                                           as ps_minutes,
    h.starts                                            as ps_starts,
    h.goals                                             as ps_goals,
    h.assists                                           as ps_assists,
    h.clean_sheets                                      as ps_clean_sheets,
    h.goals_conceded                                    as ps_goals_conceded,
    h.saves                                             as ps_saves,
    h.bonus                                             as ps_bonus,
    h.bps                                               as ps_bps,
    h.yellow_cards                                      as ps_yellow_cards,
    h.xg                                                as ps_xg,
    h.xa                                                as ps_xa,
    h.defensive_contribution                            as ps_defensive_contribution,
    h.clearances_blocks_interceptions                   as ps_cbi,
    h.tackles                                           as ps_tackles,
    h.recoveries                                        as ps_recoveries,
    h.penalties_missed                                  as ps_penalties_missed,
    coalesce(pen.penalty_goals, 0) + h.penalties_missed as ps_penalties_taken,
    case when s.matchweeks_loaded >= 38 then 1 else 0 end as ps_penalties_known,
    h.start_price                                       as ps_start_price,
    h.end_price                                         as ps_end_price,
    h.team_join_date                                    as ps_team_join_date
from {{ ref('stg_player_history_past') }} h
inner join {{ ref('players') }} p on p.p_id = h.player_id
left join {{ ref('stg_pl_penalties_by_season') }} pen
    on pen.season_label = h.history_season
    and pen.player_code = h.player_code
left join seasons s on s.season_label = h.history_season
