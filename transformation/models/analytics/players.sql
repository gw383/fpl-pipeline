-- Dimension: one row per player (prefix p_).
select
    p.player_id                              as p_id,
    p.web_name                               as p_web_name,
    concat(p.first_name, ' ', p.second_name) as p_full_name,
    p.team_id                                as p_team,
    p.position                               as p_position,
    pos.name                                 as p_position_name,
    p.price                                  as p_price,
    p.start_price                            as p_start_price,
    p.ownership                              as p_ownership,
    p.form                                   as p_form,
    p.creativity                             as p_creativity,
    p.threat                                 as p_threat,
    p.influence                              as p_influence,
    p.news                                   as p_news,
    p.news_date                              as p_news_date,
    p.status                                 as p_status,
    p.player_code                            as p_code,
    p.penalties_order                        as p_penalties_order,
    p.corners_order                          as p_corners_order,
    p.direct_freekicks_order                 as p_direct_freekicks_order,
    p.chance_of_playing                      as p_chance_of_playing
from {{ ref('stg_players') }} p
left join {{ ref('stg_positions') }} pos on pos.id = p.position
