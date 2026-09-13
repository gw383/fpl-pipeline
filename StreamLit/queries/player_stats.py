"""Query layer for the Player page: season stats, positional bests,
gameweek trend, positional rankings, and the "star" recommendation score.

Note: these queries build SQL via f-strings rather than bound
parameters. `selected_player` and `range_filter` only ever come from
Streamlit selectboxes populated from trusted, known values (see
Player.py), so this isn't exploitable today -- but it's flagged in the
project's improvement suggestions as worth tightening if this ever
takes free-text input.
"""
import pandas as pd
import streamlit as st

from database import run_query


def _range_filter_sql(range_filter: str, gw_column: str = "gw_id") -> str:
    """Build the "which gameweeks does this range include" predicate.

    `range_filter` is one of "All gameweeks", "Last 10 gameweeks" or
    "Last 5 gameweeks" (the options offered in the Player page's Range
    selectbox). Used by every query below that supports the range
    filter, so the five near-identical copies of this predicate that
    used to live in each query are now written once.
    """
    return f"""(
        '{range_filter}' = 'All gameweeks'
        or (
            '{range_filter}' = 'Last 10 gameweeks'
            and {gw_column} in (
                select top (10) gw_id
                from analytics.gameweeks
                where gw_deadline_time < cast(getdate() as datetime)
                order by gw_id desc
            )
        )
        or (
            '{range_filter}' = 'Last 5 gameweeks'
            and {gw_column} in (
                select top (5) gw_id
                from analytics.gameweeks
                where gw_deadline_time < cast(getdate() as datetime)
                order by gw_id desc
            )
        )
    )"""


@st.cache_data(ttl=600)
def get_player_stats(selected_player: str, range_filter: str) -> pd.DataFrame:
    """Season (or range-filtered) totals for one player, plus the FPL
    fantasy-points contribution of each stat category (the pf_* columns
    feed the points-breakdown chart), and the underlying xG/xA/xGA totals
    (feed the expected-vs-actual chart).

    The pf_* breakdown used to be recomputed here, in Python-generated
    SQL, on every page load. It's now summed straight out of
    analytics.player_points, a dbt model that is the single source of
    truth for "what counts as fantasy points" (see
    transformation/models/analytics/player_points.sql) -- versioned,
    dbt-tested, and no longer duplicated between this file and the dbt
    project. This also fixes a bug in the old pf_goals_conceded here: it
    was derived from pg_saves instead of pg_goals_conceded, and applied to
    every position instead of just goalkeepers/defenders. See CHANGELOG.
    """
    query = f"""
    select
        p_full_name,
        sum(ps.pg_points)                as points,
        sum(ps.pg_minutes)               as minutes,
        (count(*) * 90) - sum(ps.pg_minutes)   as minutes_not_played,
        sum(ps.pg_saves) * 90            as saves,
        sum(ps.pg_defcons)               as defcons,
        sum(ps.pg_goals)                 as goals,
        sum(ps.pg_assists)               as assists,
        sum(ps.pg_bonus)                 as bonus,
        sum(ps.pg_clean_sheets)          as clean_sheets,
        sum(ps.pg_pens_saved)            as pens_saved,
        sum(ps.pg_goals_conceded)        as goals_conceded,
        sum(ps.pg_pens_missed)           as pens_missed,
        sum(ps.pg_xG)                    as xg,
        sum(ps.pg_xA)                    as xa,
        sum(ps.pg_xGa)                   as xga,
        sum(pp.pf_minutes)            as pf_minutes,
        sum(pp.pf_cs)                 as pf_cs,
        sum(pp.pf_bonus)              as pf_bonus,
        sum(pp.pf_saves)              as pf_saves,
        sum(pp.pf_pen_saves)          as pf_pen_saves,
        sum(pp.pf_yellow)             as pf_yellow,
        sum(pp.pf_red)                as pf_red,
        sum(pp.pf_goals_conceded)     as pf_goals_conceded,
        sum(pp.pf_goals)              as pf_goals,
        sum(pp.pf_assists)            as pf_assists,
        sum(pp.pf_defcon)             as pf_defcon,
        sum(pp.pf_own_goals)          as pf_own_goals,
        sum(pp.pf_pen_missed)         as pf_pen_missed,
        sum(ps.pg_starts)                as starts
    from analytics.player_stats ps
    left join analytics.players on p_id = ps.pg_id
    left join analytics.gameweeks on ps.pg_gameweek = gw_id
    left join analytics.player_points pp
        on pp.pg_id = ps.pg_id and pp.pg_gameweek = ps.pg_gameweek
    where gw_deadline_time < cast(getdate() as datetime)
      and p_full_name = '{selected_player}'
      and {_range_filter_sql(range_filter)}
    group by p_full_name
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_best_stats(position: str, range_filter: str) -> pd.DataFrame:
    """The best season (or range-filtered) totals for `position`, used
    to normalise the player radar chart (each axis = player / best-in-position).
    """
    query = f"""
    with player_totals as (
        select
            pg_id,
            sum(pg_points)                                as points,
            sum(pg_minutes)                                as minutes,
            sum(pg_bonus)                                  as bonus,
            sum(pg_goals)                                  as goals,
            sum(pg_assists)                                as assists,
            sum(pg_clean_sheets)                           as clean_sheets,
            sum(pg_saves)                                  as saves,
            sum(pg_pens_saved)                             as pens_saved,
            sum(pg_defcons) * 90.0 / sum(pg_minutes)       as dcp90,
            sum(pg_points) * 90.0 / sum(pg_minutes)        as pp90,
            (sum(pg_points) * 90.0 / sum(pg_minutes)) / sum(p_price) as ppm90,
            sum(pg_starts)                                 as starts
        from analytics.player_stats
        left join analytics.players on pg_id = p_id
        left join analytics.positions on p_position = pos_id
        left join analytics.gameweeks on pg_gameweek = gw_id
        where pos_name = '{position}'
          and gw_deadline_time < cast(getdate() as datetime)
          and {_range_filter_sql(range_filter)}
        group by pg_id
        having sum(pg_starts) >= 1
    )
    select
        max(points)                                        as max_points,
        max(bonus)                                          as max_bonus,
        max(goals)                                          as max_goals,
        max(assists)                                        as max_assists,
        max(clean_sheets)                                   as max_cs,
        max(saves)                                          as max_saves,
        max(pens_saved)                                     as max_pens_saved,
        max(ppm90)                                          as max_ppm90,
        cast(round(max(pp90), 1) as decimal(10, 1))         as max_pp90,
        cast(round(max(dcp90), 1) as decimal(10, 1))        as max_dcp90
    from player_totals
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_gwk(selected_player: str, range_filter: str) -> pd.DataFrame:
    """Points scored by `selected_player` in each gameweek within range
    -- feeds the gameweek-trend line chart.
    """
    query = f"""
    select
        gw_id as gameweek,
        sum(pg_points) as points
    from analytics.player_stats
    left join analytics.players on pg_id = p_id
    left join analytics.gameweeks on pg_gameweek = gw_id
    where p_full_name = '{selected_player}'
      and gw_deadline_time < cast(getdate() as datetime)
      and {_range_filter_sql(range_filter)}
    group by gw_id
    order by gw_id
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_rank_metrics(selected_player: str, range_filter: str) -> pd.DataFrame:
    """`selected_player`'s rank against same-position players across a
    range of stats, plus their "points per million per 90" value
    percentile -- feeds every metric card's "#N" rank badge.
    """
    query = f"""
    with range_info as (
        select count(*) * 90.0 as max_minutes
        from analytics.gameweeks
        where gw_deadline_time < cast(getdate() as datetime)
          and {_range_filter_sql(range_filter)}
    ),

    player_totals as (
        select
            p_full_name,
            p_position,
            sum(pg_minutes)                                                    as minutes,
            sum(pg_points)                                                     as points,
            sum(pg_goals)                                                      as goals,
            sum(pg_assists)                                                    as assists,
            sum(pg_defcons)                                                    as defcons,
            sum(pg_bonus)                                                      as bonus,
            sum(pg_saves) * 90.0 / nullif(sum(pg_minutes), 0)                  as savesp90,
            sum(pg_pens_saved)                                                 as saved_pens,
            sum(pg_clean_sheets)                                               as cs,
            sum(pg_defcons) * 90.0 / nullif(sum(pg_minutes), 0)                as dcp90,
            sum(pg_points) * 90.0 / nullif(sum(pg_minutes), 0)                 as pp90,
            (sum(pg_points) * 90.0 / nullif(sum(pg_minutes), 0))
                / nullif(max(p_price), 0)                                      as ppm90
        from analytics.player_stats
        left join analytics.players on pg_id = p_id
        left join analytics.positions on p_position = pos_id
        left join analytics.gameweeks on pg_gameweek = gw_id
        where gw_deadline_time < cast(getdate() as datetime)
          and {_range_filter_sql(range_filter)}
        group by p_full_name, p_position
    ),

    player_values as (
        select
            p.*,
            cast(p.minutes as float) / nullif(r.max_minutes, 0)                as reliability,
            p.ppm90 * (cast(p.minutes as float) / nullif(r.max_minutes, 0))    as adjusted_ppm90
        from player_totals p
        cross join range_info r
    ),

    player_percentages as (
        select
            p.*,
            coalesce(round(percent_rank() over (
                partition by p.p_position
                order by p.adjusted_ppm90
            ) * 100, 1), 0) as ppm90_value
        from player_values p
    ),

    ranked_players as (
        select
            p.*,
            dense_rank() over (partition by p.p_position order by p.points desc)     as points_rank,
            dense_rank() over (partition by p.p_position order by p.goals desc)      as goals_rank,
            dense_rank() over (partition by p.p_position order by p.assists desc)    as assists_rank,
            dense_rank() over (partition by p.p_position order by p.bonus desc)      as bonus_rank,
            dense_rank() over (partition by p.p_position order by p.savesp90 desc)   as saves_rank,
            dense_rank() over (partition by p.p_position order by p.saved_pens desc) as saved_pens_rank,
            dense_rank() over (partition by p.p_position order by p.cs desc)         as cs_rank,
            dense_rank() over (partition by p.p_position order by p.defcons desc)    as defcons_rank,
            dense_rank() over (partition by p.p_position order by p.dcp90 desc)      as dcp90_rank,
            dense_rank() over (partition by p.p_position order by p.pp90 desc)       as pp90_rank,
            dense_rank() over (partition by p.p_position order by p.ppm90_value desc) as ppm90_rank
        from player_percentages p
    )

    select *
    from ranked_players
    where p_full_name = '{selected_player}'
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_star(selected_player: str) -> pd.DataFrame:
    """The "star" recommendation score (out of 10) for one player, plus
    every scoring ingredient behind it.

    This used to independently recompute the whole scoring pipeline
    (season form, last-5 form, team form, fixture difficulty) in
    Python-generated SQL every time the Player page loaded, using a
    slightly different formula from get_star_top20's Home-page version.
    Both now just read one row out of analytics.player_rating, a dbt
    model that is the single canonical implementation of this scoring
    model (see transformation/models/analytics/player_rating.sql for the
    full formula, the tunable weights, and the actual-vs-expected-points
    design). It also fixes a latent bug in the old version of this query:
    "last 5" / "next 5" gameweeks used to be computed relative to a
    hardcoded stub date ('2026-01-01') rather than the actual current date.
    """
    query = f"""
    select
        player,
        p_position,
        season_actual_score,
        season_expected_score,
        quality_score,
        last5_actual_score,
        last5_expected_score,
        recent_form_score,
        team_results_score,
        team_strength_score,
        opponent_difficulty_score,
        minutes_security_score,
        star
    from analytics.player_rating
    where player = '{selected_player}'
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_star_top5_by_position() -> pd.DataFrame:
    """The top 5 players by "star" rating, separately per position, for
    the Home page's "Top rated players" section.

    Replaces the old flat top-20-across-all-positions list
    (get_star_top20): comparing goalkeepers against forwards on the same
    single list wasn't a fair comparison (see the "why does a defender
    outrate Haaland" discussion in the project's chat history / CHANGELOG)
    -- position-by-position top 5s are a more honest read of "who's the
    best pick at each position right now".
    """
    query = """
    with ranked as (
        select
            player,
            p_position,
            star as rating,
            row_number() over (partition by p_position order by star desc) as position_rank
        from analytics.player_rating
    )
    select
        player,
        p_position,
        rating
    from ranked
    where position_rank <= 5
    order by p_position, position_rank
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_in_form_differentials(max_ownership: float = 10.0, limit: int = 20) -> pd.DataFrame:
    """Low-ownership players currently in good recent form -- candidates
    worth a look as differentials, for the Home page.

    "In form" here is recent_form_score specifically (analytics.player_rating's
    blended actual/expected points-per-90 over the last 5 gameweeks), not
    the overall star rating -- star also folds in fixture difficulty and
    team form, which would drown out "is this player playing well right
    now" with "are their next few fixtures favourable". minutes_security_score
    is still used as a floor filter (not just a display value) so a
    one-off cameo goal doesn't show up here as a nailed-on differential.
    """
    query = f"""
    select top ({limit})
        pr.player,
        pr.p_position,
        pl.p_ownership     as ownership,
        pl.p_price          as price,
        pr.recent_form_score,
        pr.star
    from analytics.player_rating pr
    left join analytics.players pl on pl.p_id = pr.p_id
    where pl.p_ownership <= {max_ownership}
      and pr.minutes_security_score >= 0.5
    order by pr.recent_form_score desc
    """
    return run_query(query)
