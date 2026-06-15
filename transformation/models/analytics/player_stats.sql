{{ config(materialized='table') }}

select
    player_id                               as pg_id,
    points                                  as pg_points,
    goals_scored                            as pg_goals,
    assists                                 as pg_assists,
    minutes                                 as pg_minutes,
    clean_sheets                            as pg_clean_sheets,
    goals_conceded                          as pg_goals_conceded,
    own_goals                               as pg_own_goals,
    penalties_saved                         as pg_pens_saved,
    penalties_missed                        as pg_pens_missed,
    yellow_cards                            as pg_yellow_cards,
    red_cards                               as pg_red_cards,
    saves                                   as pg_saves,
    bonus_points                            as pg_bonus,
    bps                                     as pg_bps,
    influence                               as pg_influence,
    creativity                              as pg_creativity,
    threat                                  as pg_threat,
    ict_index                               as pg_ict,
    defcons                                 as pg_defcons,
    starts                                  as pg_starts,
    xG                                      as pg_xG,
    xA                                      as pg_xA,
    XGI                                     as pg_XGI,
    xGa                                     as pg_xGa,
    dream_team                              as pg_dreamteam,
    played                                  as pg_played

from {{ ref('stg_player_gameweek') }} p
inner join {{ source('analytics', 'seasons') }} s
    on p.season = s.id
where cast(getdate() as date)
      between s.start_date and s.end_date;