import pandas as pd
from database import engine

def get_player_stats(selected_player, range_filter):

    query = f"""
    select p_full_name,
       sum(pg_points)                                                               as points,
       sum(pg_minutes)                                                              as minutes,
       (count(*) * 90) - sum(pg_minutes)                                            as minutes_not_played,
       sum(case
               when pg_minutes >= 1 and pg_minutes <= 60 then 1
               when pg_minutes >= 60 and pg_minutes <= 90 then 2
               when pg_minutes >= 90 and pg_minutes <= 150 then 3
               when pg_minutes >= 150 and pg_minutes <= 180 then 4
               else 0 end)                                                          as pf_minutes,
        sum(pg_saves) * 90  as saves,
        sum(pg_defcons)  as defcons,
        sum(pg_goals)  as goals,
        sum(pg_assists) as assists,
        sum(pg_bonus) as bonus,
        sum(pg_clean_sheets) as clean_sheets,
        sum(pg_pens_saved) as pens_saved,
        sum(pg_goals_conceded) as goals_conceded,
        sum(pg_pens_missed) as pens_missed,
       sum(case
               when pg_clean_sheets = 1 and p_position in (1, 2) then 4
               when pg_clean_sheets = 2 and p_position in (1, 2) then 8
               when pg_clean_sheets = 1 and p_position in (3) then 1
               when pg_clean_sheets = 2 and p_position in (3) then 2
               else 0 end)                                                          as pf_cs,
       sum(pg_bonus)                                                                as pf_bonus,
       sum(floor(pg_saves / 3.0))                                                   as pf_saves,
       sum(pg_pens_saved) * 5                                                       as pf_pen_saves,
       -sum(pg_yellow_cards)                                                        as pf_yellow,
       -sum(pg_red_cards) * 3                                                       as pf_red,
       -sum(floor(pg_saves / 2.0)) as pf_goals_conceded,
       sum(case
               when p_position = 1 then pg_goals * 10
               when p_position = 2 then pg_goals * 6
               when p_position = 3 then pg_goals * 5
               when p_position = 4 then pg_goals * 4 end)                           as pf_goals,
       sum(pg_assists) * 3                                                          as pf_assists,
       coalesce(sum(case
               when p_position = 2 then floor(pg_defcons / 10.0) * 2
               when p_position in (3, 4) then floor(pg_defcons / 12.0) * 2 end),0)    as pf_defcon,
       -sum(pg_own_goals) * 2                                                       as pf_own_goals,
       -sum(pg_pens_missed) * 2                                                     as pf_pen_missed,
       sum(pg_starts)                                                               as starts

    from analytics.player_stats
    left join analytics.players on p_id = pg_id
    left join analytics.gameweeks on pg_gameweek = gw_id
    where gw_deadline_time < cast(getdate() as date)
      and p_full_name = '{selected_player}'

      and ('{range_filter}' = 'All gameweeks'
          or
          ('{range_filter}' = 'Last 10 gameweeks'
            and gw_id in
                (select top (10) gw_id
                 from analytics.gameweeks
                 where gw_deadline_time < cast(getdate() as date)
                 order by gw_id desc))
          or
          ('{range_filter}' = 'Last 5 gameweeks'
            and gw_id in
                (select top (5) gw_id
                 from analytics.gameweeks
                 where gw_deadline_time < cast(getdate() as date)
                 order by gw_id desc)))
    group by p_full_name;
        """

    return pd.read_sql(query, engine)

def get_best_stats(position, range_filter):

    query = f"""
with player_totals as
(select
        pg_id,
        sum(pg_points) AS points,
        sum(pg_minutes) AS minutes,
        sum(pg_bonus) AS bonus,
        sum(pg_goals) as goals,
        sum(pg_assists) as assists,
        sum(pg_clean_sheets) as clean_sheets,
        sum(pg_saves) as saves,
        sum(pg_pens_saved) as pens_saved,
        sum(pg_defcons) * 90.0 / sum(pg_minutes) AS dcp90,
        sum(pg_points) * 90.0 / sum(pg_minutes) AS pp90,
        (sum(pg_points) * 90.0 / sum(pg_minutes)) / sum(p_price) AS ppm90,
        sum(pg_starts) AS starts
    from analytics.player_stats
    left join analytics.players on pg_id = p_id
    left join analytics.positions on p_position = pos_id
    left join analytics.gameweeks on pg_gameweek = gw_id
    where pos_name = '{position}' and gw_deadline_time < cast(getdate() as date)
      and ('{range_filter}' = 'All gameweeks' or
          ('{range_filter}' = 'Last 10 gameweeks'
                and gw_id in
                (select top(10) gw_id
                    from analytics.gameweeks
                    where gw_deadline_time < cast(getdate() as date)
                    order by gw_id desc))
      or
          ('{range_filter}' = 'Last 5 gameweeks'
                and gw_id in
                (select top(5) gw_id
                    from analytics.gameweeks
                    where gw_deadline_time < cast(getdate() as date)
                    order by gw_id desc)))
    group by pg_id
    having sum(pg_starts) >= 5)
select
    max(points) AS max_points,
    max(bonus) AS max_bonus,
    max(goals) AS max_goals,
    max(assists) AS max_assists,
    max(clean_sheets) as max_cs,
    max(saves) as max_saves,
    max(pens_saved) as max_pens_saved,
    max(ppm90) as max_ppm90,
    cast(round(max(pp90),1) as decimal(10,1)) as max_pp90,
    cast(round(max(dcp90),1) as decimal(10,1)) AS max_dcp90
from player_totals;
        """

    return pd.read_sql(query, engine)

def get_gwk(selected_player, range_filter):

    query = f"""
select
    gw_id as gameweek,
    sum(pg_points) as points
from analytics.player_stats
left join analytics.players
    on pg_id = p_id
left join analytics.gameweeks
    on pg_gameweek = gw_id
where p_full_name = '{selected_player}'
  and gw_deadline_time < cast(getdate() as date)
      and ('{range_filter}' = 'All gameweeks'
          or
          ('{range_filter}' = 'Last 10 gameweeks'
            and gw_id in
                (select top (10) gw_id
                 from analytics.gameweeks
                 where gw_deadline_time < cast(getdate() as date)
                 order by gw_id desc))
          or
          ('{range_filter}' = 'Last 5 gameweeks'
            and gw_id in
                (select top (5) gw_id
                 from analytics.gameweeks
                 where gw_deadline_time < cast(getdate() as date)
                 order by gw_id desc)))
group by gw_id
order by gw_id;
        """

    return pd.read_sql(query, engine)

def get_rank_metrics(selected_player, range_filter):

    query = f"""
with range_info as
(select
    count(*) * 90.0 as max_minutes
from analytics.gameweeks
where gw_deadline_time < cast(getdate() as date)
      and ('{range_filter}' = 'All gameweeks' or
          ('{range_filter}' = 'Last 10 gameweeks'
                and gw_id in
                (select top(10) gw_id
                 from analytics.gameweeks
                 where gw_deadline_time < cast(getdate() as date)
                 order by gw_id desc))
          or
          ('{range_filter}' = 'Last 5 gameweeks'
                and gw_id in
                (select top(5) gw_id
                 from analytics.gameweeks
                 where gw_deadline_time < cast(getdate() as date)
                 order by gw_id desc)))),

player_totals as
(select
    p_full_name,
    p_position,
    sum(pg_minutes) as minutes,
    sum(pg_points) as points,
    sum(pg_goals) as goals,
    sum(pg_assists) as assists,
    sum(pg_defcons) as defcons,
    sum(pg_bonus) as bonus,
    sum(pg_saves) * 90.0 / nullif(sum(pg_minutes),0) as savesp90,
    sum(pg_pens_saved) as saved_pens,
    sum(pg_clean_sheets) as cs,
    sum(pg_defcons) * 90.0 / nullif(sum(pg_minutes),0) as dcp90,
    sum(pg_points) * 90.0 / nullif(sum(pg_minutes),0) as pp90,
    (sum(pg_points) * 90.0 / nullif(sum(pg_minutes),0)) / nullif(max(p_price),0) as ppm90
from analytics.player_stats
    left join analytics.players on pg_id = p_id
    left join analytics.positions on p_position = pos_id
    left join analytics.gameweeks on pg_gameweek = gw_id
where gw_deadline_time < cast(getdate() as date)
      and ('{range_filter}' = 'All gameweeks' or
          ('{range_filter}' = 'Last 10 gameweeks'
                and gw_id in
                (select top(10) gw_id
                 from analytics.gameweeks
                 where gw_deadline_time < cast(getdate() as date)
                 order by gw_id desc))
          or
          ('{range_filter}' = 'Last 5 gameweeks'
                and gw_id in
                (select top(5) gw_id
                 from analytics.gameweeks
                 where gw_deadline_time < cast(getdate() as date)
                 order by gw_id desc)))
group by p_full_name, p_position
),
player_values as
(select
    p.*,
    cast(p.minutes as float) / nullif(r.max_minutes,0) as reliability,
    p.ppm90 * (cast(p.minutes as float) / nullif(r.max_minutes,0)) as adjusted_ppm90
from player_totals p
    cross join range_info r),

player_percentages as
(select
    p.*,
    coalesce(round(percent_rank() over(
        partition by p.p_position
        order by p.adjusted_ppm90
    ) * 100,1),0) as ppm90_value
from player_values p),

ranked_players as
(select
    p.*,
    dense_rank() over(partition by p.p_position order by p.points desc) as points_rank,
    dense_rank() over(partition by p.p_position order by p.goals desc) as goals_rank,
    dense_rank() over(partition by p.p_position order by p.assists desc) as assists_rank,
    dense_rank() over(partition by p.p_position order by p.bonus desc) as bonus_rank,
    dense_rank() over(partition by p.p_position order by p.savesp90 desc) as saves_rank,
    dense_rank() over(partition by p.p_position order by p.saved_pens desc) as saved_pens_rank,
    dense_rank() over(partition by p.p_position order by p.cs desc) as cs_rank,
    dense_rank() over(partition by p.p_position order by p.defcons desc) as defcons_rank,
    dense_rank() over(partition by p.p_position order by p.dcp90 desc) as dcp90_rank,
    dense_rank() over(partition by p.p_position order by p.pp90 desc) as pp90_rank,
    dense_rank() over(partition by p.p_position order by p.ppm90_value desc) as ppm90_rank
from player_percentages p
)
select *
from ranked_players
where p_full_name = '{selected_player}'
        """

    return pd.read_sql(query, engine)

def get_star(selected_player):

    query = f"""
with last5 as
(select top(5)
    gw_id
from analytics.gameweeks
where gw_deadline_time < '2026-01-01'
order by gw_id desc),

next5 as
(select top(5)
    gw_id
from analytics.gameweeks
where gw_deadline_time > '2026-01-01'
order by gw_id),

team_results as
(select
    f_home_team as team_id,
    f_gameweek as gameweek,
    f_home_score as goals_for,
    f_away_score as goals_against,
    case
        when f_home_score > f_away_score then 3
        when f_home_score = f_away_score then 1
        else 0
    end as result_points,
    case when f_away_score = 0 then 1 else 0 end as clean_sheet

from analytics.fixtures

left join last5
    on f_gameweek = gw_id

where f_finished = 1
and gw_id is not null
union all
select
    f_away_team as team_id,
    f_gameweek as gameweek,
    f_away_score as goals_for,
    f_home_score as goals_against,
    case
        when f_away_score > f_home_score then 3
        when f_away_score = f_home_score then 1
        else 0
    end as result_points,
    case when f_home_score = 0 then 1 else 0 end as clean_sheet

from analytics.fixtures

left join last5
    on f_gameweek = gw_id

where f_finished = 1
and gw_id is not null),

team_form as
(select
    team_id,
    sum(goals_for) as goals_scored,
    sum(goals_against) as goals_conceded,
    sum(result_points) as league_points,
    sum(clean_sheet) as clean_sheets

from team_results

group by team_id),

player_team_form as
(select
    p_team,
    goals_scored as team_last5_goals,
    league_points as team_last5_points,
    goals_conceded as team_last5_conceded

from analytics.players p

left join team_form tf
    on p.p_team = tf.team_id

where p_full_name = '{selected_player}'),

team_form_scores as
(select
    p_team,

    case
        when team_last5_goals / 5.0 >= 3 then 10
        when team_last5_goals / 5.0 >= 2.7 then 9
        when team_last5_goals / 5.0 >= 2.4 then 8
        when team_last5_goals / 5.0 >= 2.1 then 7
        when team_last5_goals / 5.0 >= 1.8 then 6
        when team_last5_goals / 5.0 >= 1.5 then 5
        when team_last5_goals / 5.0 >= 1.2 then 4
        when team_last5_goals / 5.0 >= 0.9 then 3
        when team_last5_goals / 5.0 >= 0.6 then 2
        when team_last5_goals / 5.0 >= 0.3 then 1
        else 0
    end as goals_score,

    case
        when team_last5_conceded / 5.0 >= 2.7 then 1
        when team_last5_conceded / 5.0 >= 2.4 then 2
        when team_last5_conceded / 5.0 >= 2.1 then 3
        when team_last5_conceded / 5.0 >= 1.8 then 4
        when team_last5_conceded / 5.0 >= 1.5 then 5
        when team_last5_conceded / 5.0 >= 1.2 then 6
        when team_last5_conceded / 5.0 >= 0.9 then 7
        when team_last5_conceded / 5.0 >= 0.6 then 8
        when team_last5_conceded / 5.0 >= 0.3 then 9
        else 10
    end as gc_score,

    case
        when team_last5_points = 15 then 10
        when team_last5_points = 13 then 9
        when team_last5_points = 12 then 8
        when team_last5_points = 11 then 7
        when team_last5_points in (9,10) then 6
        when team_last5_points in (7,8) then 5
        when team_last5_points in (5,6) then 4
        when team_last5_points in (3,4) then 3
        when team_last5_points = 2 then 2
        when team_last5_points = 1 then 1
        else 0
    end as points_score

from player_team_form),

team_form_final as
(select
    tfs.p_team,

    case
        when pl.p_position in (3,4) then
            (goals_score * 0.5)
            +
            (points_score * 0.5)

        when pl.p_position in (1,2) then
            (gc_score * 0.5)
            +
            (points_score * 0.5)

        else 0
    end as team_form_score

from team_form_scores tfs

left join analytics.players pl
    on tfs.p_team = pl.p_team

where pl.p_full_name = '{selected_player}'),

upcoming_fixtures as
(select
    case
        when f_home_team = p_team then f_away_team
        else f_home_team
    end as opponent,

    case
        when f_home_team = p_team then f_home_diff
        else f_away_diff
    end as difficulty

from analytics.fixtures

cross join analytics.players

left join next5
    on f_gameweek = gw_id

where p_full_name = '{selected_player}'
and next5.gw_id is not null
and (f_home_team = p_team or f_away_team = p_team)),

opponent_form as
(select
    avg(cast(goals_scored as decimal(10,2))) as opponent_goals_scored,
    avg(cast(goals_conceded as decimal(10,2))) as opponent_goals_conceded,
    avg(cast(league_points as decimal(10,2))) as opponent_points,
    avg(cast(difficulty as decimal(10,2))) as opponent_fixture_difficulty

from upcoming_fixtures u

left join team_form tf
    on u.opponent = tf.team_id),

player_metrics as
(select
    p_full_name as player,
    p.p_team,
    p_position,

    sum(pg_points) as total_points,
case
    when sum(case when l.gw_id is not null then pg_minutes else 0 end) < 30
        then 0

    else
        coalesce(
            sum(case when l.gw_id is not null then pg_points else 0 end)
            * 90.0 /
            nullif(
                sum(case when l.gw_id is not null then pg_minutes else 0 end),
                0
            ),
            0
        )
end as last5_form,

    tf.team_form_score,
    ofm.opponent_goals_scored,
    ofm.opponent_fixture_difficulty,
    ofm.opponent_goals_conceded,
    ofm.opponent_points
from analytics.players p
left join analytics.player_stats
    on p_id = pg_id
left join analytics.gameweeks gw
    on gw.gw_id = pg_gameweek
left join last5 l
    on gw.gw_id = l.gw_id
left join team_form_final tf
    on p.p_team = tf.p_team
cross join opponent_form ofm

group by
    p_full_name,
    p.p_team,
    p_position,
    tf.team_form_score,
    ofm.opponent_goals_scored,
    ofm.opponent_goals_conceded,
    ofm.opponent_points,
    ofm.opponent_fixture_difficulty),

season_percentiles as
(
select
    pm.*,
    case when total_points = 0 then 0
        else percent_rank() over(order by total_points) * 10 end as season_form_score
from player_metrics pm
where total_points > 0
),

form_scores as
(
select
    pm.*,

    coalesce(sp.season_form_score,0) as season_form_score,

    case
        when pm.last5_form + 3 > 10 then 10
        when pm.last5_form = 0 then 0
        else pm.last5_form + 3
    end as last5_form_score
from player_metrics pm
left join season_percentiles sp
    on pm.player = sp.player
    and pm.p_team = sp.p_team)

select
    player,
    p_position,
    round(season_form_score,2) as season_form_score,
    round(last5_form_score,2) as last5_form_score,
    round(team_form_score,2) as team_form_score,

    round(
        10 - ((opponent_fixture_difficulty - 2.5) * 4)
    ,2) as opponent_difficulty_score,

    round(
        (season_form_score * 0.50) +
        (last5_form_score * 0.25) +
        (team_form_score * 0.10) +
        ((10 - ((opponent_fixture_difficulty - 2.5) * 4)) * 0.15)
    ,2) as star

from form_scores

where player = '{selected_player}';
        """

    return pd.read_sql(query, engine)




