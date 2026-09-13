{{
    config(
        materialized='incremental',
        unique_key=['pg_id', 'pg_gameweek'],
        incremental_strategy='delete+insert'
    )
}}

-- Per-player-per-gameweek fantasy-points breakdown, derived from the raw
-- per-gameweek stats in analytics.player_stats and each player's position.
--
-- This is the single source of truth for "what counts as fantasy points"
-- in this project. It used to be implemented as raw SQL inside
-- StreamLit/queries/player_stats.py (recomputed on every dashboard page
-- load, untested); it's now a versioned, tested dbt model instead, and
-- the Streamlit query layer just sums these columns over whatever
-- gameweek range the user picks.
--
-- pf_goals_conceded fixes a bug found in the original Streamlit-only
-- implementation, which derived goals-conceded points from `pg_saves`
-- instead of `pg_goals_conceded`, and applied them to every position
-- instead of just goalkeepers/defenders (the only positions that lose
-- points for goals conceded in real FPL scoring). See CHANGELOG.
--
-- Incremental: once a gameweek's data has been loaded and this table
-- has been built at least once, only gameweeks from the last 10 days
-- are reprocessed on subsequent runs (recent gameweeks can still have
-- their bonus points/stats corrected by FPL for a day or two after
-- kickoff; anything older is treated as final). Run
-- `dbt run --full-refresh --select player_points` to force a full
-- rebuild, e.g. after a season's worth of scoring-rule changes.

select
    ps.pg_id       as pg_id,
    ps.pg_gameweek as pg_gameweek,
    ps.pg_points   as pg_points,
    ps.pg_starts   as pg_starts,
    p.p_position   as p_position,

    -- Minutes: 1 point for 1-59 minutes, 2 points for 60+. The bands
    -- above 90 handle a double gameweek, where the API's per-event
    -- stats for a player can combine two matches' minutes.
    case
        when ps.pg_minutes >= 1   and ps.pg_minutes <= 60  then 1
        when ps.pg_minutes >= 60  and ps.pg_minutes <= 90  then 2
        when ps.pg_minutes >= 90  and ps.pg_minutes <= 150 then 3
        when ps.pg_minutes >= 150 and ps.pg_minutes <= 180 then 4
        else 0
    end as pf_minutes,

    -- Clean sheets: goalkeepers/defenders earn 4 (8 for two clean
    -- sheets in one gameweek row, i.e. a double gameweek), midfielders
    -- earn 1 (2), forwards earn none.
    case
        when ps.pg_clean_sheets = 1 and p.p_position in (1, 2) then 4
        when ps.pg_clean_sheets = 2 and p.p_position in (1, 2) then 8
        when ps.pg_clean_sheets = 1 and p.p_position = 3       then 1
        when ps.pg_clean_sheets = 2 and p.p_position = 3       then 2
        else 0
    end as pf_cs,

    ps.pg_bonus as pf_bonus,

    -- Saves: 1 point per 3 saves, calculated per gameweek rather than
    -- on a season total -- flooring here and summing later gives the
    -- same result as flooring a running total would, since FPL awards
    -- save points per match, not retroactively across the season.
    floor(ps.pg_saves / 3.0) as pf_saves,

    ps.pg_pens_saved * 5  as pf_pen_saves,
    -ps.pg_yellow_cards   as pf_yellow,
    -ps.pg_red_cards * 3  as pf_red,

    -- Goals conceded: only goalkeepers/defenders lose points for this,
    -- 1 point per 2 goals conceded.
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

    -- Defensive contributions: defenders need 10 actions per 2 points,
    -- midfielders/forwards need 12; goalkeepers don't earn these.
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
where gw.gw_deadline_time >= dateadd(day, -10, getdate())
{% endif %}
