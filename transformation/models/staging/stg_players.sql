-- One row per player in the current season: identity, team, position,
-- price, ownership, availability, set-piece duties (FPL's order of choice
-- for penalties, corners/indirect free kicks and direct free kicks; 1 =
-- first choice) and FPL's own season-to-date form metrics.
select
    p.id                                 as player_id,
    p.web_name                           as web_name,
    p.first_name                         as first_name,
    p.second_name                        as second_name,
    p.known_name                         as known_name,
    p.team                               as team_id,
    p.element_type                       as position,
    p.form                               as form,
    p.photo                              as photo,
    cast(p.now_cost as float) / 10       as price,
    (cast(p.now_cost as float) - cast(p.cost_change_start as float)) / 10 as start_price,
    cast(p.selected_by_percent as float) as ownership,
    cast(p.creativity as float)          as creativity,
    cast(p.threat as float)              as threat,
    cast(p.influence as float)           as influence,
    p.news                               as news,
    p.news_added                         as news_date,
    p.status                             as status,
    p.code                               as player_code,
    p.penalties_order                    as penalties_order,
    p.corners_and_indirect_freekicks_order as corners_order,
    p.direct_freekicks_order             as direct_freekicks_order,
    cast(p.chance_of_playing_next_round as float) as chance_of_playing,
    s.id                                 as season
from {{ source('raw', 'raw_players') }} p
{{ join_current_season('p') }}
