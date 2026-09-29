{{
    config(
        materialized='incremental',
        unique_key=['pg_id', 'pg_gameweek'],
        incremental_strategy='delete+insert'
    )
}}

-- Fact: each player's fantasy points per gameweek, broken down by scoring
-- category (pf_*). The single source of truth for "where did the points
-- come from"; the dashboard sums these columns over any gameweek range.
--
-- Rows are one per player per gameweek, so a double gameweek's stats are
-- the combined total of both matches; the bands and thresholds below
-- account for that where they can.
--
-- Incremental: after the first build only gameweeks whose deadline falls
-- inside the `player_points_lookback_days` window are rebuilt, matching the
-- period in which FPL (and the extraction pipeline's grace window) can
-- still revise recent stats. `dbt run --full-refresh -s player_points`
-- rebuilds everything, e.g. after a scoring-rule change.

select
    ps.pg_id       as pg_id,
    ps.pg_gameweek as pg_gameweek,
    ps.pg_points   as pg_points,
    ps.pg_starts   as pg_starts,
    p.p_position   as p_position,

    -- Minutes: 1 point for 1-59 minutes, 2 points for 60+. The bands
    -- above 90 approximate a double gameweek's combined minutes.
    case
        when ps.pg_minutes >= 1   and ps.pg_minutes < 60   then 1
        when ps.pg_minutes >= 60  and ps.pg_minutes <= 90  then 2
        when ps.pg_minutes >= 90  and ps.pg_minutes <= 150 then 3
        when ps.pg_minutes >= 150 and ps.pg_minutes <= 180 then 4
        else 0
    end as pf_minutes,

    -- Clean sheets: GK/DEF earn 4, MID 1, FWD 0 (doubled for two clean
    -- sheets in a double gameweek).
    case
        when ps.pg_clean_sheets = 1 and p.p_position in (1, 2) then 4
        when ps.pg_clean_sheets = 2 and p.p_position in (1, 2) then 8
        when ps.pg_clean_sheets = 1 and p.p_position = 3       then 1
        when ps.pg_clean_sheets = 2 and p.p_position = 3       then 2
        else 0
    end as pf_cs,

    ps.pg_bonus as pf_bonus,

    -- Saves: 1 point per 3 saves, awarded per match (so floored per
    -- gameweek, never on a season total).
    floor(ps.pg_saves / 3.0) as pf_saves,

    ps.pg_pens_saved * 5  as pf_pen_saves,
    -ps.pg_yellow_cards   as pf_yellow,
    -ps.pg_red_cards * 3  as pf_red,

    -- Goals conceded: GK/DEF lose 1 point per 2 goals conceded.
    case
        when p.p_position in (1, 2) then -floor(ps.pg_goals_conceded / 2.0)
        else 0
    end as pf_goals_conceded,

    case
        when p.p_position = 1 then ps.pg_goals * 10
        when p.p_position = 2 then ps.pg_goals * 6
        when p.p_position = 3 then ps.pg_goals * 5
        when p.p_position = 4 then ps.pg_goals * 4
        else 0
    end as pf_goals,

    ps.pg_assists * 3 as pf_assists,

    -- Defensive contributions: 2 points for every 10 actions (DEF) or 12
    -- actions (MID/FWD); goalkeepers can't earn these.
    case
        when p.p_position = 2      then floor(ps.pg_defcons / 10.0) * 2
        when p.p_position in (3, 4) then floor(ps.pg_defcons / 12.0) * 2
        else 0
    end as pf_defcon,

    -ps.pg_own_goals * 2   as pf_own_goals,
    -ps.pg_pens_missed * 2 as pf_pen_missed

from {{ ref('player_stats') }} ps
left join {{ ref('players') }} p on ps.pg_id = p.p_id
left join {{ ref('gameweeks') }} gw on ps.pg_gameweek = gw.gw_id

{% if is_incremental() %}
where gw.gw_deadline_time >= dateadd(day, -{{ var('player_points_lookback_days') }}, getdate())
{% endif %}
