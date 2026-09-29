-- Fact: one row per team per gameweek with the team's underlying numbers.
--
-- team_xg / team_xa are summed over every player who played: each player's
-- figure is their own share of the team total. team_xga is the xG the
-- opponent(s) created in the same gameweek. (Each player's own xGA only
-- covers the minutes he was on the pitch, so averaging it across a squad
-- understates the true figure whenever substitutes are used.)
--
-- In a double gameweek these are the combined figures for both matches. If
-- the opponent also played twice that gameweek, only its per-match average
-- is counted against this team.
with team_totals as (
    select
        p.p_team         as team_id,
        ps.pg_gameweek   as gw_id,
        sum(ps.pg_xG)    as team_xg,
        sum(ps.pg_xA)    as team_xa
    from {{ ref('player_stats') }} ps
    inner join {{ ref('players') }} p on p.p_id = ps.pg_id
    where ps.pg_minutes > 0
    group by p.p_team, ps.pg_gameweek
),

team_opponents as (
    select f_home_team as team_id, f_away_team as opponent_id, f_gameweek as gw_id
    from {{ ref('fixtures') }}

    union all

    select f_away_team as team_id, f_home_team as opponent_id, f_gameweek as gw_id
    from {{ ref('fixtures') }}
),

fixtures_per_gameweek as (
    select team_id, gw_id, count(*) as fixture_count
    from team_opponents
    group by team_id, gw_id
)

select
    t.team_id,
    t.gw_id,
    t.team_xg,
    t.team_xa,
    sum(o.team_xg / fpg.fixture_count) as team_xga
from team_totals t
left join team_opponents op
    on op.team_id = t.team_id
    and op.gw_id = t.gw_id
left join team_totals o
    on o.team_id = op.opponent_id
    and o.gw_id = t.gw_id
left join fixtures_per_gameweek fpg
    on fpg.team_id = op.opponent_id
    and fpg.gw_id = t.gw_id
group by t.team_id, t.gw_id, t.team_xg, t.team_xa
