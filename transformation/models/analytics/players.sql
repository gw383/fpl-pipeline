{{ config(materialized='table') }}

select
    player_id                               as p_id,
    web_name                                as p_web_name,
    concat(first_name,' ', second_name)     as p_full_name,
    team_id                                 as p_team,
    position                                as p_position,
    price                                   as p_price,
    form                                    as p_form,
    creativity                              as p_creativity,
    threat                                  as p_threat,
    influence                               as p_influence,
    news                                    as p_news,
    news_date                               as p_news_date
from {{ ref('stg_players') }} p
inner join {{ source('analytics', 'seasons') }} s
    on p.season = s.id
where cast(getdate() as date)
      between s.start_date and s.end_date;