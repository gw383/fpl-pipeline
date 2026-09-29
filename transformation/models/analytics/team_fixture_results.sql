-- Fact: one row per team per finished fixture, seen from that team's side
-- (so every match appears twice): venue, opponent, score, W/D/L, and the
-- team's underlying xG/xA/xGA for that gameweek.
--
-- The underlying numbers come from team_gameweek_stats, which cannot split
-- a double gameweek into its two matches: both fixtures of a double
-- gameweek carry the same combined figures (flagged by is_double_gw), so
-- divide by fixtures_in_gw before summing across rows.
with team_fixtures as (
    select
        f_id,
        f_home_team   as team_id,
        f_gameweek    as gw_id,
        'H'           as venue,
        f_away_team   as opponent_id,
        f_home_score  as own_score,
        f_away_score  as opp_score
    from {{ ref('fixtures') }}
    where f_finished = 1

    union all

    select
        f_id,
        f_away_team   as team_id,
        f_gameweek    as gw_id,
        'A'           as venue,
        f_home_team   as opponent_id,
        f_away_score  as own_score,
        f_home_score  as opp_score
    from {{ ref('fixtures') }}
    where f_finished = 1
),

fixtures_per_gameweek as (
    select
        team_id,
        gw_id,
        count(*) as fixture_count
    from team_fixtures
    group by team_id, gw_id
)

select
    tf.f_id,
    tf.team_id,
    tf.gw_id,
    tf.venue,
    tf.opponent_id,
    tf.own_score,
    tf.opp_score,
    case
        when tf.own_score > tf.opp_score then 'W'
        when tf.own_score < tf.opp_score then 'L'
        else 'D'
    end                                                 as result,
    coalesce(tgs.team_xg, 0)                            as team_xg,
    coalesce(tgs.team_xa, 0)                            as team_xa,
    coalesce(tgs.team_xga, 0)                           as team_xga,
    fpg.fixture_count                                   as fixtures_in_gw,
    case when fpg.fixture_count > 1 then 1 else 0 end   as is_double_gw
from team_fixtures tf
left join {{ ref('team_gameweek_stats') }} tgs
    on tgs.team_id = tf.team_id
    and tgs.gw_id = tf.gw_id
left join fixtures_per_gameweek fpg
    on fpg.team_id = tf.team_id
    and fpg.gw_id = tf.gw_id
