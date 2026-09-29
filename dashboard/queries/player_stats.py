"""Player-level statistics, positional rankings and ratings (expected points
from analytics.player_rating, written by projections/run.py)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from database import run_query
from queries.common import PLAYED_GAMEWEEKS_SQL, range_filter_sql
from settings import CACHE_TTL_SECONDS

# Per-90 rates (defensive actions, saves, points) are only ranked for players
# with a meaningful share of the minutes in the selected range: at least
# PER_90_MIN_SHARE of every available minute, and never less than
# PER_90_MIN_MINUTES. Otherwise a 10-minute cameo with a few clearances tops
# the table. Players below the bar get no per-90 rank.
PER_90_MIN_SHARE = 0.25
PER_90_MIN_MINUTES = 90


def per_90_min_minutes_sql(range_label: str) -> str:
    """SQL expression for the minimum minutes needed to be ranked on a per-90
    rate over ``range_label`` (scales with the played gameweeks in range)."""
    return f"""(
        select case
            when count(*) * 90 * {PER_90_MIN_SHARE} > {PER_90_MIN_MINUTES} then count(*) * 90 * {PER_90_MIN_SHARE}
            else {PER_90_MIN_MINUTES}
        end
        from analytics.gameweeks gw_r
        where gw_r.{PLAYED_GAMEWEEKS_SQL}
          and {range_filter_sql(range_label, "gw_r.gw_id")}
    )"""


# Columns behind a rating, as needed by components/rating_breakdown.py.
RATING_COLUMNS = """
    star,
    xpts_next_gw,
    xpts_horizon,
    xpts_per_gw,
    xmins_next_gw,
    availability_next_gw,
    fixtures_in_horizon,
    pts_appearance,
    pts_goals,
    pts_assists,
    pts_penalties,
    pts_clean_sheet,
    pts_goals_conceded,
    pts_saves,
    pts_defcon,
    pts_bonus,
    pts_cards,
    xg_horizon,
    xa_horizon,
    xpens_horizon,
    star_typical_xpts,
    star_best_xpts
"""


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_player_stats(player_id: int, range_label: str) -> pd.DataFrame:
    """Totals over the selected range: raw stats, underlying xG/xA/xGA, and
    fantasy points by scoring category (pf_*, from analytics.player_points)."""
    return run_query(
        f"""
        select
            sum(ps.pg_points)                     as points,
            sum(ps.pg_minutes)                    as minutes,
            count(*) * 90 - sum(ps.pg_minutes)    as minutes_not_played,
            sum(ps.pg_saves)                      as saves,
            sum(ps.pg_defcons)                    as defcons,
            sum(ps.pg_goals)                      as goals,
            sum(ps.pg_assists)                    as assists,
            sum(ps.pg_bonus)                      as bonus,
            sum(ps.pg_clean_sheets)               as clean_sheets,
            sum(ps.pg_pens_saved)                 as pens_saved,
            sum(ps.pg_goals_conceded)             as goals_conceded,
            sum(ps.pg_starts)                     as starts,
            sum(ps.pg_xG)                         as xg,
            sum(ps.pg_xA)                         as xa,
            sum(ps.pg_xGa)                        as xga,
            sum(pp.pf_minutes)                    as pf_minutes,
            sum(pp.pf_cs)                         as pf_cs,
            sum(pp.pf_bonus)                      as pf_bonus,
            sum(pp.pf_saves)                      as pf_saves,
            sum(pp.pf_pen_saves)                  as pf_pen_saves,
            sum(pp.pf_yellow)                     as pf_yellow,
            sum(pp.pf_red)                        as pf_red,
            sum(pp.pf_goals_conceded)             as pf_goals_conceded,
            sum(pp.pf_goals)                      as pf_goals,
            sum(pp.pf_assists)                    as pf_assists,
            sum(pp.pf_defcon)                     as pf_defcon,
            sum(pp.pf_own_goals)                  as pf_own_goals,
            sum(pp.pf_pen_missed)                 as pf_pen_missed
        from analytics.player_stats ps
        inner join analytics.gameweeks gw on gw.gw_id = ps.pg_gameweek
        left join analytics.player_points pp
            on pp.pg_id = ps.pg_id
            and pp.pg_gameweek = ps.pg_gameweek
        where ps.pg_id = :player_id
          and gw.{PLAYED_GAMEWEEKS_SQL}
          and {range_filter_sql(range_label, "ps.pg_gameweek")}
        having count(*) > 0
        """,
        {"player_id": player_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_best_stats(position_name: str, range_label: str) -> pd.DataFrame:
    """The best totals in a position over the range -- the scale for the
    player radar chart (each axis is player / best in position)."""
    return run_query(
        f"""
        with player_totals as (
            select
                ps.pg_id,
                sum(ps.pg_points)                                          as points,
                sum(ps.pg_bonus)                                           as bonus,
                sum(ps.pg_goals)                                           as goals,
                sum(ps.pg_assists)                                         as assists,
                sum(ps.pg_clean_sheets)                                    as clean_sheets,
                sum(ps.pg_saves)                                           as saves,
                sum(ps.pg_pens_saved)                                      as pens_saved,
                case
                    when sum(ps.pg_minutes) >= {per_90_min_minutes_sql(range_label)}
                    then sum(ps.pg_defcons) * 90.0 / sum(ps.pg_minutes)
                end                                                        as dcp90
            from analytics.player_stats ps
            inner join analytics.players p on p.p_id = ps.pg_id
            inner join analytics.gameweeks gw on gw.gw_id = ps.pg_gameweek
            where p.p_position_name = :position_name
              and gw.{PLAYED_GAMEWEEKS_SQL}
              and {range_filter_sql(range_label, "ps.pg_gameweek")}
            group by ps.pg_id
            having sum(ps.pg_starts) >= 1
        )
        select
            max(points)                                  as max_points,
            max(bonus)                                   as max_bonus,
            max(goals)                                   as max_goals,
            max(assists)                                 as max_assists,
            max(clean_sheets)                            as max_cs,
            max(saves)                                   as max_saves,
            max(pens_saved)                              as max_pens_saved,
            cast(round(max(dcp90), 1) as decimal(10, 1)) as max_dcp90
        from player_totals
        """,
        {"position_name": position_name},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_gameweek_points(player_id: int, range_label: str) -> pd.DataFrame:
    """Points per played gameweek within the range, for the trend chart."""
    return run_query(
        f"""
        select
            ps.pg_gameweek    as gameweek,
            sum(ps.pg_points) as points
        from analytics.player_stats ps
        inner join analytics.gameweeks gw on gw.gw_id = ps.pg_gameweek
        where ps.pg_id = :player_id
          and gw.{PLAYED_GAMEWEEKS_SQL}
          and {range_filter_sql(range_label, "ps.pg_gameweek")}
        group by ps.pg_gameweek
        order by ps.pg_gameweek
        """,
        {"player_id": player_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_rank_metrics(player_id: int, range_label: str) -> pd.DataFrame:
    """The player's rank within their position on each headline stat over
    the range. Ties are broken by current form, then name, so every player
    gets a distinct, stable rank. Per-90 ranks are null for players under
    the minutes bar (see ``per_90_min_minutes_sql``)."""
    return run_query(
        f"""
        with player_totals as (
            select
                p.p_id,
                p.p_full_name,
                p.p_position,
                sum(ps.pg_points)                                          as points,
                sum(ps.pg_goals)                                           as goals,
                sum(ps.pg_assists)                                         as assists,
                sum(ps.pg_bonus)                                           as bonus,
                sum(ps.pg_defcons)                                         as defcons,
                sum(ps.pg_minutes)                                         as minutes,
                sum(ps.pg_saves) * 90.0 / nullif(sum(ps.pg_minutes), 0)    as savesp90,
                sum(ps.pg_pens_saved)                                      as saved_pens,
                sum(ps.pg_clean_sheets)                                    as cs,
                sum(ps.pg_defcons) * 90.0 / nullif(sum(ps.pg_minutes), 0)  as dcp90,
                sum(ps.pg_points) * 90.0 / nullif(sum(ps.pg_minutes), 0)   as pp90,
                max(p.p_form)                                              as form_value
            from analytics.player_stats ps
            inner join analytics.players p on p.p_id = ps.pg_id
            inner join analytics.gameweeks gw on gw.gw_id = ps.pg_gameweek
            where gw.{PLAYED_GAMEWEEKS_SQL}
              and {range_filter_sql(range_label, "ps.pg_gameweek")}
            group by p.p_id, p.p_full_name, p.p_position
        ),

        -- Per-90 rates only count for players over the minutes bar.
        qualified as (
            select
                *,
                case when minutes >= {per_90_min_minutes_sql(range_label)} then 1 else 0 end as per_90_qualified
            from player_totals
        ),

        ranked as (
            select
                p_id,
                row_number() over (partition by p_position order by points desc,     form_value desc, p_full_name) as points_rank,
                row_number() over (partition by p_position order by goals desc,      form_value desc, p_full_name) as goals_rank,
                row_number() over (partition by p_position order by assists desc,    form_value desc, p_full_name) as assists_rank,
                row_number() over (partition by p_position order by bonus desc,      form_value desc, p_full_name) as bonus_rank,
                case when per_90_qualified = 1 then row_number() over (
                    partition by p_position, per_90_qualified order by savesp90 desc, form_value desc, p_full_name
                ) end as saves_rank,
                row_number() over (partition by p_position order by saved_pens desc, form_value desc, p_full_name) as saved_pens_rank,
                row_number() over (partition by p_position order by cs desc,         form_value desc, p_full_name) as cs_rank,
                row_number() over (partition by p_position order by defcons desc,    form_value desc, p_full_name) as defcons_rank,
                case when per_90_qualified = 1 then row_number() over (
                    partition by p_position, per_90_qualified order by dcp90 desc, form_value desc, p_full_name
                ) end as dcp90_rank,
                case when per_90_qualified = 1 then row_number() over (
                    partition by p_position, per_90_qualified order by pp90 desc, form_value desc, p_full_name
                ) end as pp90_rank,
                row_number() over (partition by p_position order by form_value desc, points desc,     p_full_name) as form_rank
            from qualified
        )

        select *
        from ranked
        where p_id = :player_id
        """,
        {"player_id": player_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_star(player_id: int) -> pd.DataFrame:
    """One player's rating and the expected points behind it."""
    return run_query(
        f"""
        select player, p_position, p_penalties_order, {RATING_COLUMNS}
        from analytics.player_rating
        where p_id = :player_id
        """,
        {"player_id": player_id},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_top_rated(per_position: int | None = None, position: int | None = None) -> pd.DataFrame:
    """Players ordered by expected points over the projection horizon within
    each position, with team, price and value.

    ``per_position`` caps how many are returned per position; ``position``
    (1-4, GK..FWD) restricts the result to one position.
    """
    return run_query(
        f"""
        select
            pr.p_id,
            pr.player,
            p.p_web_name as web_name,
            pr.p_position,
            pr.star as rating,
            pr.p_penalties_order,
            {RATING_COLUMNS},
            t.team_short_name,
            p.p_price as price,
            pr.xpts_horizon / nullif(p.p_price, 0) as xpts_per_million,
            pr.position_rank
        from analytics.player_rating pr
        inner join analytics.players p on p.p_id = pr.p_id
        left join analytics.teams t on t.team_id = p.p_team
        where (:position is null or pr.p_position = :position)
          and (:per_position is null or pr.position_rank <= :per_position)
        order by pr.p_position, pr.position_rank
        """,
        {"position": position, "per_position": per_position},
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_in_form_differentials(max_ownership: float = 10.0, limit: int = 20) -> pd.DataFrame:
    """Low-ownership players with the most expected points over the
    projection horizon, among those expected to play most of next week."""
    return run_query(
        """
        select top (:limit)
            pr.p_id,
            pr.player,
            pr.p_position,
            pl.p_ownership   as ownership,
            pl.p_price       as price,
            pr.xpts_horizon
        from analytics.player_rating pr
        inner join analytics.players pl on pl.p_id = pr.p_id
        where pl.p_ownership <= :max_ownership
          and pr.xmins_next_gw >= 60
        order by pr.xpts_horizon desc
        """,
        {"max_ownership": max_ownership, "limit": limit},
    )
