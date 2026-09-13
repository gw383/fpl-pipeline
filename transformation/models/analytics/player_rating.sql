{{ config(materialized='table') }}

-- Unified "star" recommendation score (0-10) for every player, blending:
--   * season form        (50%) -- percentile rank of total points this season
--   * last-5-gameweek form (25%) -- points per 90 over the last 5 played gameweeks
--   * team form          (10%) -- the player's team's results over those same gameweeks
--   * fixture difficulty (15%) -- average difficulty of the player's next 5 fixtures
--
-- This replaces two separate, slightly different formulas that used to
-- live in StreamLit/queries/player_stats.py: get_star (used on the
-- Player page, weighted as above) and get_star_top20 (used on the Home
-- page leaderboard, which used a simpler team-form calculation, no
-- fixture-difficulty term, and different weights: 50/25/25). Both pages
-- now read from this one table, so a player's rating is always
-- consistent wherever it's shown -- see CHANGELOG for the reconciliation
-- decision and what to double-check.
--
-- Also fixes a latent issue in the original get_star: it identified
-- "last 5" / "next 5" gameweeks relative to a hardcoded stub date
-- (2026-01-01) rather than the actual current date, so it would already
-- be picking the wrong gameweeks today. This model uses getdate(), like
-- every other "current" filter in this project.

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

team_results as (
    select
        f_home_team  as team_id,
        f_home_score as goals_for,
        f_away_score as goals_against,
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
        f_away_score as goals_for,
        f_home_score as goals_against,
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
        sum(goals_for)      as goals_scored,
        sum(goals_against)  as goals_conceded,
        sum(result_points)  as league_points
    from team_results
    group by team_id
),

team_form_scores as (
    select
        team_id,

        case
            when goals_scored / 5.0 >= 3   then 10
            when goals_scored / 5.0 >= 2.7 then 9
            when goals_scored / 5.0 >= 2.4 then 8
            when goals_scored / 5.0 >= 2.1 then 7
            when goals_scored / 5.0 >= 1.8 then 6
            when goals_scored / 5.0 >= 1.5 then 5
            when goals_scored / 5.0 >= 1.2 then 4
            when goals_scored / 5.0 >= 0.9 then 3
            when goals_scored / 5.0 >= 0.6 then 2
            when goals_scored / 5.0 >= 0.3 then 1
            else 0
        end as goals_score,

        case
            when goals_conceded / 5.0 >= 2.7 then 1
            when goals_conceded / 5.0 >= 2.4 then 2
            when goals_conceded / 5.0 >= 2.1 then 3
            when goals_conceded / 5.0 >= 1.8 then 4
            when goals_conceded / 5.0 >= 1.5 then 5
            when goals_conceded / 5.0 >= 1.2 then 6
            when goals_conceded / 5.0 >= 0.9 then 7
            when goals_conceded / 5.0 >= 0.6 then 8
            when goals_conceded / 5.0 >= 0.3 then 9
            else 10
        end as gc_score,

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
        end as points_score

    from team_form
),

-- Team form is weighted differently by position (attackers care about
-- their team's goals scored; defenders/goalkeepers care about goals
-- conceded), so this is computed per player, not just per team.
player_team_form as (
    select
        pl.p_id,
        case
            when pl.p_position in (3, 4) then (tfs.goals_score * 0.5) + (tfs.points_score * 0.5)
            when pl.p_position in (1, 2) then (tfs.gc_score * 0.5) + (tfs.points_score * 0.5)
            else 0
        end as team_form_score
    from {{ ref('players') }} pl
    left join team_form_scores tfs on pl.p_team = tfs.team_id
),

upcoming_fixtures as (
    select
        p.p_id,
        case when f.f_home_team = p.p_team then f.f_away_team else f.f_home_team end as opponent,
        case when f.f_home_team = p.p_team then f.f_home_diff else f.f_away_diff end as difficulty
    from {{ ref('players') }} p
    inner join {{ ref('fixtures') }} f
        on f.f_home_team = p.p_team or f.f_away_team = p.p_team
    inner join next5 on f.f_gameweek = next5.gw_id
),

opponent_form as (
    select
        u.p_id,
        avg(cast(u.difficulty as decimal(10, 2))) as opponent_fixture_difficulty
    from upcoming_fixtures u
    group by u.p_id
),

player_metrics as (
    select
        p.p_id,
        p.p_full_name as player,
        p.p_position,

        sum(ps.pg_points) as total_points,

        case
            when sum(case when l.gw_id is not null then ps.pg_minutes else 0 end) < 30 then 0
            else coalesce(
                sum(case when l.gw_id is not null then ps.pg_points else 0 end) * 90.0
                / nullif(sum(case when l.gw_id is not null then ps.pg_minutes else 0 end), 0),
                0
            )
        end as last5_form,

        max(ptf.team_form_score)               as team_form_score,
        max(ofm.opponent_fixture_difficulty)   as opponent_fixture_difficulty

    from {{ ref('players') }} p
    left join {{ ref('player_stats') }} ps on p.p_id = ps.pg_id
    left join {{ ref('gameweeks') }} gw on gw.gw_id = ps.pg_gameweek
    left join last5 l on gw.gw_id = l.gw_id
    left join player_team_form ptf on p.p_id = ptf.p_id
    left join opponent_form ofm on p.p_id = ofm.p_id

    group by p.p_id, p.p_full_name, p.p_position
),

season_percentiles as (
    select
        pm.p_id,
        case
            when total_points = 0 then 0
            else percent_rank() over (order by total_points) * 10
        end as season_form_score
    from player_metrics pm
    where total_points > 0
),

form_scores as (
    select
        pm.*,
        coalesce(sp.season_form_score, 0) as season_form_score,
        case
            when pm.last5_form + 3 > 10 then 10
            when pm.last5_form = 0 then 0
            else pm.last5_form + 3
        end as last5_form_score
    from player_metrics pm
    left join season_percentiles sp on pm.p_id = sp.p_id
)

select
    p_id,
    player,
    p_position,
    round(season_form_score, 2) as season_form_score,
    round(last5_form_score, 2) as last5_form_score,
    round(coalesce(team_form_score, 0), 2) as team_form_score,
    round(10 - ((coalesce(opponent_fixture_difficulty, 2.5) - 2.5) * 4), 2) as opponent_difficulty_score,
    round(
        (season_form_score * 0.50)
        + (last5_form_score * 0.25)
        + (coalesce(team_form_score, 0) * 0.10)
        + ((10 - ((coalesce(opponent_fixture_difficulty, 2.5) - 2.5) * 4)) * 0.15)
    , 2) as star
from form_scores
