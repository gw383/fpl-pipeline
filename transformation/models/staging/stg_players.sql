{{ config(materialized='view') }}

select 
    p.id                            as player_id,
    web_name                        as web_name,
    first_name                      as first_name,
    second_name                     as second_name,
    known_name                      as known_name,
    team                            as team_id,
    element_type                    as position,
    form                            as form,
    photo                           as photo,
    now_cost/10                     as price,
    selected_by_percent             as ownership,
    cast(creativity as float)       as creativity,
    cast(threat as float)           as threat,
    cast(influence as float)        as influence,
    news                            as news,
    news_added                      as news_date,
    s.id                     as season
from {{ source('raw', 'raw_players') }} p
inner join {{ source('analytics', 'seasons') }} s
    on p.season = s.display_name;