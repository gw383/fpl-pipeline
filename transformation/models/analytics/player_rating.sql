{{ config(materialized='table') }}

-- =============================================================================
-- TUNABLE WEIGHTS -- this is the only section you should need to touch to
-- try different pictures of "how good is this player to transfer in".
-- Every weight below is a plain number between 0 and 1; each labelled group
-- must sum to 1.0 (a comment above each group says so). Change a number,
-- re-run `dbt run --select player_rating`, reload the dashboard.
-- =============================================================================

-- Top-level blend: how much each of the five ingredients counts towards
-- the final 0-10 star. Must sum to 1.0.
{% set WEIGHT_QUALITY        = 0.40 %}  -- season-long quality (actual points blended with expected points)
{% set WEIGHT_RECENT         = 0.30 %}  -- last-5-gameweek form (same actual/expected blend, per-90)
{% set WEIGHT_TEAM_RESULTS   = 0.05 %}  -- the player's team's own match results (W/D/L) over the last 5 gameweeks
{% set WEIGHT_TEAM_STRENGTH  = 0.05 %}  -- how strong the player's team is, proxied by how hard other teams rate them as an opponent
{% set WEIGHT_FIXTURES       = 0.20 %}  -- how easy/hard the player's next 5 fixtures are

-- Within "quality" and within "recent form": how much weight goes on what
-- actually happened (actual points) vs. what the underlying process says
-- should have happened (expected points, from xG/xA/xGA). Each pair must
-- sum to 1.0. A player who *consistently* beats their expected points is
-- arguably a clinical finisher rather than a lucky one -- that's exactly
-- why actual points is kept in the blend at all rather than replaced
-- outright by expected points -- but weighting expected points more
-- heavily overall tilts the rating towards being predictive of *future*
-- points rather than just rewarding points already banked (which are
-- more exposed to one-off variance: a deflection, a hot streak of
-- finishing, a purple patch of bonus points).
{% set QUALITY_ACTUAL_WEIGHT   = 0.45 %}
{% set QUALITY_EXPECTED_WEIGHT = 0.55 %}
{% set FORM_ACTUAL_WEIGHT      = 0.40 %}
{% set FORM_EXPECTED_WEIGHT    = 0.60 %}

-- Minutes-security gate (see minutes_security CTE below). This is applied
-- as a final multiplier on the whole star, not as one ingredient among
-- others -- the idea is that a brilliant underlying rating means nothing
-- if the player isn't actually going to be on the pitch, so this scales
-- the whole recommendation down rather than getting diluted into an
-- average with everything else.
{% set MINUTES_PER_MATCH      = 90 %}   -- minutes in a full match, used to size "fully nailed on" against however many gameweeks the last5 window actually contains (see note below)
{% set MINUTES_SECURITY_FLOOR = 0.3 %}  -- lowest the minutes-based part of the gate can fall to (never zeroes a player out solely for a quiet patch of minutes)
{% set NEWS_LOOKBACK_DAYS     = 7 %}    -- how recent a news/injury flag has to be to count against a player
{% set INJURY_NEWS_MULTIPLIER = 0.4 %}  -- extra multiplier applied on top when there's a live news/injury flag

-- Minimum minutes in the last 5 gameweeks before a per-90 form rate is
-- trusted at all (below this, the rate is treated as "no data" rather
-- than an inflated small-sample number -- one 20-minute cameo with a
-- goal should not read as a 12-points-per-90 player).
{% set MIN_MINUTES_FOR_FORM_RATE = 90 %}

-- =============================================================================
-- Everything below implements the blend above. You shouldn't need to
-- change anything past this point just to try different weightings.
-- =============================================================================

with last5 as (
    select top (5) gw_id
    from {{ ref('gameweeks') }}
    where gw_deadline_time < getdate()
    order by gw_id desc
),

next5 as (
    select top (5) gw_id
    from {{ ref('gameweeks') }}
    where gw_deadline_time > getdate()
    order by gw_id
),

-- Per-player-per-gameweek actual points (straight from player_points, the
-- project's single source of truth for "what counts as fantasy points")
-- alongside an *expected* points figure built with the same formula, but
-- swapping in xG/xA/xGA wherever an underlying-process stat exists
-- (goals, assists, goals conceded). Everything else -- minutes, clean
-- sheets, bonus, saves, cards, defensive contributions, own goals, missed
-- pens -- has no meaningful "expected" version, so both figures share
-- those categories unchanged; they only diverge on the three process-driven
-- categories, which is exactly where "was this luck or is it repeatable"
-- is the interesting question.
player_points_expected as (
    select
        pp.pg_id,
        pp.pg_gameweek,
        pp.p_position,

        pp.pf_minutes + pp.pf_cs + pp.pf_bonus + pp.pf_saves + pp.pf_pen_saves
            + pp.pf_yellow + pp.pf_red + pp.pf_goals + pp.pf_assists
            + pp.pf_goals_conceded + pp.pf_defcon + pp.pf_own_goals + pp.pf_pen_missed
            as actual_points,

        pp.pf_minutes + pp.pf_cs + pp.pf_bonus + pp.pf_saves + pp.pf_pen_saves
            + pp.pf_yellow + pp.pf_red + pp.pf_defcon + pp.pf_own_goals + pp.pf_pen_missed
            + case pp.p_position
                when 1 then ps.pg_xG * 10
                when 2 then ps.pg_xG * 6
                when 3 then ps.pg_xG * 5
                when 4 then ps.pg_xG * 4
                else 0
              end
            + (ps.pg_xA * 3)
            + case
                when pp.p_position in (1, 2) then -floor(ps.pg_xGa / 2.0)
                else 0
              end
            as expected_points

    from {{ ref('player_points') }} pp
    left join {{ ref('player_stats') }} ps
        on ps.pg_id = pp.pg_id and ps.pg_gameweek = pp.pg_gameweek
),

-- One row per player: season totals (actual + expected) and the same two
-- figures restricted to the last 5 gameweeks, plus how many minutes they
-- actually played in that window (used both to gate the per-90 rate below
-- and to drive the minutes-security multiplier later).
player_totals as (
    select
        p.p_id,
        p.p_full_name as player,
        p.p_position,

        sum(ppe.actual_points)   as season_actual_points,
        sum(ppe.expected_points) as season_expected_points,

        sum(case when l.gw_id is not null then ps.pg_minutes else 0 end)     as last5_minutes,
        sum(case when l.gw_id is not null then ppe.actual_points else 0 end)   as last5_actual_points,
        sum(case when l.gw_id is not null then ppe.expected_points else 0 end) as last5_expected_points

    from {{ ref('players') }} p
    left join player_points_expected ppe on ppe.pg_id = p.p_id
    left join {{ ref('player_stats') }} ps
        on ps.pg_id = ppe.pg_id and ps.pg_gameweek = ppe.pg_gameweek
    left join {{ ref('gameweeks') }} gw on gw.gw_id = ppe.pg_gameweek
    left join last5 l on l.gw_id = gw.gw_id

    group by p.p_id, p.p_full_name, p.p_position
),

-- Last-5 per-90 rates, gated by MIN_MINUTES_FOR_FORM_RATE so a tiny cameo
-- can't produce an absurd rate. Below the threshold the rate is treated
-- as "no data" (0) rather than a noisy extrapolation.
form_rates as (
    select
        pt.*,
        case
            when pt.last5_minutes < {{ MIN_MINUTES_FOR_FORM_RATE }} then 0
            else pt.last5_actual_points * 90.0 / nullif(pt.last5_minutes, 0)
        end as last5_actual_p90,
        case
            when pt.last5_minutes < {{ MIN_MINUTES_FOR_FORM_RATE }} then 0
            else pt.last5_expected_points * 90.0 / nullif(pt.last5_minutes, 0)
        end as last5_expected_p90
    from player_totals pt
),

-- Four independent percentile scores (0-10), each computed *within
-- position* (a good defender should be judged against other defenders,
-- not against forwards who structurally score more raw points) and each
-- only ranked among players who actually have a non-zero value -- players
-- with nothing to show yet default to 0 rather than diluting everyone
-- else's percentile.
season_actual_percentiles as (
    select p_id, percent_rank() over (partition by p_position order by season_actual_points) * 10 as score
    from player_totals
    where season_actual_points > 0
),

season_expected_percentiles as (
    select p_id, percent_rank() over (partition by p_position order by season_expected_points) * 10 as score
    from player_totals
    where season_expected_points > 0
),

last5_actual_percentiles as (
    select p_id, percent_rank() over (partition by p_position order by last5_actual_p90) * 10 as score
    from form_rates
    where last5_actual_p90 > 0
),

last5_expected_percentiles as (
    select p_id, percent_rank() over (partition by p_position order by last5_expected_p90) * 10 as score
    from form_rates
    where last5_expected_p90 > 0
),

-- Team results over the same last-5 window: pure match results (win/
-- draw/loss), from actual fixtures. This deliberately does NOT look at
-- goals scored/conceded any more -- if a player is personally scoring
-- goals or keeping clean sheets, that's already fully captured by their
-- own quality/recent-form scores above, so folding the team's goals
-- into this too was largely double-counting the same signal. What
-- isn't already captured anywhere else is simply "is this player's team
-- winning matches" -- results can diverge from the underlying goal
-- difference (a scrappy 1-0 win still banks 3 points), so it earns its
-- own small slice of the rating.
team_results as (
    select
        f_home_team  as team_id,
        case
            when f_home_score > f_away_score then 3
            when f_home_score = f_away_score then 1
            else 0
        end as result_points
    from {{ ref('fixtures') }} f
    inner join last5 on f.f_gameweek = last5.gw_id
    where f.f_finished = 1

    union all

    select
        f_away_team  as team_id,
        case
            when f_away_score > f_home_score then 3
            when f_away_score = f_home_score then 1
            else 0
        end as result_points
    from {{ ref('fixtures') }} f
    inner join last5 on f.f_gameweek = last5.gw_id
    where f.f_finished = 1
),

team_form as (
    select
        team_id,
        sum(result_points) as league_points
    from team_results
    group by team_id
),

team_results_scores as (
    select
        team_id,
        case
            when league_points = 15       then 10
            when league_points = 13       then 9
            when league_points = 12       then 8
            when league_points = 11       then 7
            when league_points in (9, 10) then 6
            when league_points in (7, 8)  then 5
            when league_points in (5, 6)  then 4
            when league_points in (3, 4)  then 3
            when league_points = 2        then 2
            when league_points = 1        then 1
            else 0
        end as team_results_score
    from team_form
),

player_team_results as (
    select
        pl.p_id,
        coalesce(trs.team_results_score, 0) as team_results_score
    from {{ ref('players') }} pl
    left join team_results_scores trs on pl.p_team = trs.team_id
),

-- Fixture difficulty over the player's own team's next 5 fixtures, from
-- the team's OWN perspective -- how hard are these upcoming games for
-- them personally. f_home_diff/f_away_diff follow the same convention
-- used everywhere else in the project (see StreamLit/queries/player_info.py's
-- get_next_5 and StreamLit/queries/team_data.py's get_team_fixtures):
-- f_home_diff is the difficulty AS SEEN BY the home team (i.e. it
-- reflects how strong the away opponent is), and f_away_diff is the
-- difficulty AS SEEN BY the away team (reflecting how strong the home
-- opponent is). So a team's own difficulty for a fixture is f_home_diff
-- when they're at home, f_away_diff when they're away.
--
-- Computed per TEAM first (an explicit UNION ALL of the home leg and
-- away leg, exactly like team_results above and team_as_opponent below)
-- rather than as a single players-join-fixtures query keyed off
-- "f_home_team = p_team OR f_away_team = p_team": that OR-based join is
-- what the previous version of this CTE used, and it turned out to
-- give every player the exact same averaged difficulty regardless of
-- team once actually run -- rewriting it in the same per-team-then-join
-- shape already used successfully elsewhere in this file avoids
-- whatever was going wrong with the OR condition (and is a previous,
-- separate bug fix from the branch-swap noted in the CHANGELOG: this
-- CTE has now been touched twice -- once for reading the wrong side of
-- each fixture, once for this join rewrite).
team_upcoming_fixtures as (
    select
        f_home_team as team_id,
        f_home_diff as difficulty
    from {{ ref('fixtures') }} f
    inner join next5 on f.f_gameweek = next5.gw_id

    union all

    select
        f_away_team as team_id,
        f_away_diff as difficulty
    from {{ ref('fixtures') }} f
    inner join next5 on f.f_gameweek = next5.gw_id
),

opponent_form as (
    select
        pl.p_id,
        avg(cast(tuf.difficulty as decimal(10, 2))) as opponent_fixture_difficulty
    from {{ ref('players') }} pl
    left join team_upcoming_fixtures tuf on tuf.team_id = pl.p_team
    group by pl.p_id
),

-- Team strength, proxied by how difficult *other* teams have found this
-- team to play against over the same last-5 window used for results
-- above -- i.e. the OPPONENT's perspective on facing this team, not
-- this team's own perspective on its fixtures (that's
-- team_upcoming_fixtures/opponent_form above, which is a different
-- question about a different, future, window). Using the same
-- home/away-diff convention: when this team
-- plays at home, the away side's rating of that fixture (f_away_diff)
-- is their read on how hard THIS team is; when this team plays away,
-- the home side's rating (f_home_diff) is their read on how hard THIS
-- team is. A team that's a tough, high-difficulty opponent for everyone
-- else is (by FPL's own crowd-sourced difficulty logic) a strong team;
-- a team that's an easy fixture for everyone else is a weak one.
team_as_opponent as (
    select
        f_home_team as team_id,
        f_away_diff as difficulty_facing_this_team
    from {{ ref('fixtures') }} f
    inner join last5 on f.f_gameweek = last5.gw_id
    where f.f_finished = 1

    union all

    select
        f_away_team as team_id,
        f_home_diff as difficulty_facing_this_team
    from {{ ref('fixtures') }} f
    inner join last5 on f.f_gameweek = last5.gw_id
    where f.f_finished = 1
),

team_strength as (
    select
        team_id,
        avg(cast(difficulty_facing_this_team as decimal(10, 2))) as avg_difficulty_as_opponent
    from team_as_opponent
    group by team_id
),

team_strength_scores as (
    select
        team_id,
        -- Difficulty ratings run 1 (easiest opponent) to 5 (hardest
        -- opponent), so this is just a straight-line rescale onto the
        -- usual 0-10 scale: 1 -> 0, 3 -> 5, 5 -> 10. Clamped in case a
        -- team's average lands fractionally outside 1-5.
        case
            when (avg_difficulty_as_opponent - 1) * 2.5 > 10 then 10
            when (avg_difficulty_as_opponent - 1) * 2.5 < 0  then 0
            else (avg_difficulty_as_opponent - 1) * 2.5
        end as team_strength_score
    from team_strength
),

player_team_strength as (
    select
        pl.p_id,
        coalesce(tss.team_strength_score, 0) as team_strength_score
    from {{ ref('players') }} pl
    left join team_strength_scores tss on pl.p_team = tss.team_id
),

-- How many gameweeks the "last5" window actually contains. Early in a
-- season (or straight after a run of postponements/blank gameweeks)
-- there may be fewer than 5 gameweeks with a deadline in the past yet --
-- "last5" is still called that, but might only hold 3 or 4 rows. Sizing
-- the minutes-security gate off a fixed 5-match assumption in that case
-- would score *every* nailed-on player identically below 1.0, purely
-- because there haven't been 5 gameweeks to play yet -- not because
-- they've missed any minutes. This makes the "fully nailed on" bar match
-- however many gameweeks are actually available.
last5_window_size as (
    select count(*) as gws from last5
),

-- Minutes-security gate: how much to trust this player's rating at all,
-- given how nailed-on they've recently been and whether there's a live
-- news/injury flag against them. This is applied multiplicatively to the
-- final star, not blended in as an ingredient -- see the comment on
-- MINUTES_PER_MATCH above for why.
minutes_security as (
    select
        pt.p_id,
        case
            when pt.last5_minutes >= (l5w.gws * {{ MINUTES_PER_MATCH }}) then 1.0
            else {{ MINUTES_SECURITY_FLOOR }}
                + (1.0 - {{ MINUTES_SECURITY_FLOOR }})
                * (cast(pt.last5_minutes as float) / nullif(l5w.gws * {{ MINUTES_PER_MATCH }}, 0))
        end
        *
        -- p_news_date (raw_players.news_added) is stored as text, not a
        -- native datetime column -- the FPL API returns it as an ISO-8601
        -- string with a trailing "Z" (e.g. "2026-09-10T18:15:23.912108Z"),
        -- which SQL Server's implicit string->datetime conversion can't
        -- parse, and fails the whole query (error 241) rather than just
        -- this one column. try_convert(..., 127) parses that exact ISO-8601
        -- format explicitly and returns NULL instead of erroring for
        -- anything it can't parse (including an empty string), which is
        -- also why the null-check below tests the converted value rather
        -- than the raw string.
        case
            when pl.p_news is not null and pl.p_news <> ''
                 and try_convert(datetime2, pl.p_news_date, 127) is not null
                 and try_convert(datetime2, pl.p_news_date, 127) >= dateadd(day, -{{ NEWS_LOOKBACK_DAYS }}, getdate())
            then {{ INJURY_NEWS_MULTIPLIER }}
            else 1.0
        end as minutes_security_score
    from player_totals pt
    left join {{ ref('players') }} pl on pl.p_id = pt.p_id
    cross join last5_window_size l5w
),

-- The five 0-10 ingredients, computed once each so the final select
-- doesn't need to repeat any of this arithmetic.
component_scores as (
    select
        pt.p_id,
        pt.player,
        pt.p_position,

        round(coalesce(sap.score, 0), 2) as season_actual_score,
        round(coalesce(sep.score, 0), 2) as season_expected_score,
        (coalesce(sap.score, 0) * {{ QUALITY_ACTUAL_WEIGHT }})
            + (coalesce(sep.score, 0) * {{ QUALITY_EXPECTED_WEIGHT }})
            as quality_score,

        round(coalesce(lap.score, 0), 2) as last5_actual_score,
        round(coalesce(lep.score, 0), 2) as last5_expected_score,
        (coalesce(lap.score, 0) * {{ FORM_ACTUAL_WEIGHT }})
            + (coalesce(lep.score, 0) * {{ FORM_EXPECTED_WEIGHT }})
            as recent_form_score,

        coalesce(ptr.team_results_score, 0) as team_results_score,
        coalesce(pts.team_strength_score, 0) as team_strength_score,

        -- Explicitly clamped to 0-10: the original version of this model
        -- could exceed 10 here for a very easy run of fixtures, which
        -- meant the final star could silently exceed its documented
        -- 0-10 scale.
        case
            when (10 - ((coalesce(ofm.opponent_fixture_difficulty, 2.5) - 2.5) * 4)) > 10 then 10
            when (10 - ((coalesce(ofm.opponent_fixture_difficulty, 2.5) - 2.5) * 4)) < 0  then 0
            else (10 - ((coalesce(ofm.opponent_fixture_difficulty, 2.5) - 2.5) * 4))
        end as opponent_difficulty_score,

        coalesce(ms.minutes_security_score, 1.0) as minutes_security_score

    from player_totals pt
    left join season_actual_percentiles   sap on sap.p_id = pt.p_id
    left join season_expected_percentiles sep on sep.p_id = pt.p_id
    left join last5_actual_percentiles    lap on lap.p_id = pt.p_id
    left join last5_expected_percentiles  lep on lep.p_id = pt.p_id
    left join player_team_results          ptr on ptr.p_id = pt.p_id
    left join player_team_strength         pts on pts.p_id = pt.p_id
    left join opponent_form                ofm on ofm.p_id = pt.p_id
    left join minutes_security            ms  on ms.p_id = pt.p_id
)

select
    p_id,
    player,
    p_position,

    season_actual_score,
    season_expected_score,
    round(quality_score, 2) as quality_score,

    last5_actual_score,
    last5_expected_score,
    round(recent_form_score, 2) as recent_form_score,

    round(team_results_score, 2) as team_results_score,
    round(team_strength_score, 2) as team_strength_score,
    round(opponent_difficulty_score, 2) as opponent_difficulty_score,
    round(minutes_security_score, 2) as minutes_security_score,

    -- Final star: the five weighted ingredients above (each already
    -- clamped to 0-10, and WEIGHT_QUALITY + WEIGHT_RECENT +
    -- WEIGHT_TEAM_RESULTS + WEIGHT_TEAM_STRENGTH + WEIGHT_FIXTURES sums
    -- to 1.0, so this weighted sum can't itself exceed 10), scaled down
    -- by the minutes-security gate. The outer case is a defensive clamp
    -- in case the weights above are retuned to no longer sum to exactly
    -- 1.0.
    round(
        case
            when (
                (quality_score * {{ WEIGHT_QUALITY }})
                + (recent_form_score * {{ WEIGHT_RECENT }})
                + (team_results_score * {{ WEIGHT_TEAM_RESULTS }})
                + (team_strength_score * {{ WEIGHT_TEAM_STRENGTH }})
                + (opponent_difficulty_score * {{ WEIGHT_FIXTURES }})
            ) * minutes_security_score > 10 then 10
            when (
                (quality_score * {{ WEIGHT_QUALITY }})
                + (recent_form_score * {{ WEIGHT_RECENT }})
                + (team_results_score * {{ WEIGHT_TEAM_RESULTS }})
                + (team_strength_score * {{ WEIGHT_TEAM_STRENGTH }})
                + (opponent_difficulty_score * {{ WEIGHT_FIXTURES }})
            ) * minutes_security_score < 0 then 0
            else (
                (quality_score * {{ WEIGHT_QUALITY }})
                + (recent_form_score * {{ WEIGHT_RECENT }})
                + (team_results_score * {{ WEIGHT_TEAM_RESULTS }})
                + (team_strength_score * {{ WEIGHT_TEAM_STRENGTH }})
                + (opponent_difficulty_score * {{ WEIGHT_FIXTURES }})
            ) * minutes_security_score
        end
    , 2) as star

from component_scores
