{{ config(materialized='table') }}

-- Dimension table: one row per player, prefixed p_.
--
-- p_ownership (selected_by_percent from the FPL API) was added to support
-- a "differential" view -- low-ownership, in-form players -- on the Home
-- page; it was already captured in stg_players but wasn't previously
-- carried through to this table.
select
    player_id                            as p_id,
    web_name                             as p_web_name,
    concat(first_name, ' ', second_name) as p_full_name,
    team_id                              as p_team,
    position                             as p_position,
    price                                as p_price,
    ownership                            as p_ownership,
    form                                 as p_form,
    creativity                          as p_creativity,
    threat                               as p_threat,
    influence                            as p_influence,
    news                                 as p_news,
    news_date                            as p_news_date
from {{ ref('stg_players') }} p
inner join {{ ref('seasons') }} s
    on p.season = s.id
where cast(getdate() as date) between s.start_date and s.end_date
