{{ config(materialized='table') }}

-- One row per tracked manager, per player currently in their 15-man
-- squad (their most recently ingested gameweek's picks only -- see
-- latest_gw below), joined out to full player/team identity and this
-- project's own star rating. Feeds the My Team page's pitch view
-- (starting XI + bench) and captain/vice-captain badges.
--
-- squad_position is FPL's own squad-management slot number (1-11 =
-- starting XI in ascending sub-priority order for the bench, 12-15 =
-- bench, 12 first). It is NOT a football position/formation slot --
-- that's p_position (from analytics.players, GK/DEF/MID/FWD), which is
-- what the pitch view groups players by, same as the Home page's Best
-- XI already does. is_starting is derived here once so nothing
-- downstream needs to remember "<=11 means starting" itself.
--
-- multiplier reflects FPL's own post-match auto-substitution bookkeeping
-- once a gameweek is finished (e.g. a benched player who was subbed in
-- shows multiplier=1, the starter they replaced shows 0) -- this model
-- doesn't attempt to reimplement FPL's own auto-sub rules, it just
-- carries through whatever the API already resolved.
with latest_gw as (
    -- Each manager's most recent gameweek with ingested picks -- "my
    -- current team" advances automatically as the season progresses
    -- and extraction/manager_picks.py ingests each new gameweek, with
    -- no manual "which gameweek is current" tracking needed here.
    select
        entry_id,
        max(gw_id) as gw_id
    from {{ ref('stg_manager_picks') }}
    group by entry_id
)

select
    mp.entry_id                                        as m_id,
    mp.gw_id                                            as gw_id,
    mp.squad_position                                   as squad_position,
    case when mp.squad_position <= 11 then 1 else 0 end as is_starting,
    mp.is_captain                                       as is_captain,
    mp.is_vice_captain                                   as is_vice_captain,
    mp.multiplier                                        as multiplier,
    p.p_id                                                as p_id,
    p.p_full_name                                         as player,
    p.p_web_name                                          as web_name,
    p.p_position                                          as p_position,
    p.p_team                                              as team_id,
    t.team_name                                           as team_name,
    t.team_short_name                                     as team_short_name,
    pr.star                                               as star
from {{ ref('stg_manager_picks') }} mp
inner join latest_gw lg
    on lg.entry_id = mp.entry_id and lg.gw_id = mp.gw_id
left join {{ ref('players') }} p on p.p_id = mp.player_id
left join {{ ref('teams') }} t on t.team_id = p.p_team
left join {{ ref('player_rating') }} pr on pr.p_id = mp.player_id
