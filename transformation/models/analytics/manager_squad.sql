-- Each tracked manager's current 15-man squad: the picks from their most
-- recently ingested gameweek, joined to player/team identity. Feeds the
-- dashboard's My Team page (which adds each player's rating from
-- analytics.player_rating, written by projections/run.py).

-- Materialised as a view (not a table like the rest of analytics) so a
-- manager the dashboard loads on demand appears as soon as their raw rows
-- are written, without waiting for the next dbt run.
{{ config(materialized='view') }}

with latest_gw as (
    select
        entry_id,
        max(gw_id) as gw_id
    from {{ ref('stg_manager_picks') }}
    group by entry_id
)

select
    mp.entry_id                                         as m_id,
    mp.gw_id                                            as gw_id,
    mp.squad_position                                   as squad_position,
    case when mp.squad_position <= 11 then 1 else 0 end as is_starting,
    mp.is_captain                                       as is_captain,
    mp.is_vice_captain                                  as is_vice_captain,
    mp.multiplier                                       as multiplier,
    p.p_id                                              as p_id,
    p.p_full_name                                       as player,
    p.p_web_name                                        as web_name,
    p.p_position                                        as p_position,
    p.p_team                                            as team_id,
    t.team_name                                         as team_name,
    t.team_short_name                                   as team_short_name
from {{ ref('stg_manager_picks') }} mp
inner join latest_gw lg
    on lg.entry_id = mp.entry_id
    and lg.gw_id = mp.gw_id
left join {{ ref('players') }} p on p.p_id = mp.player_id
left join {{ ref('teams') }} t on t.team_id = p.p_team
