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


