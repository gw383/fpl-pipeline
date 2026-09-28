"""Query layer for the Team page: team identity, recency-ranged league
results (score, goalscorers/assisters, underlying xG/xA/xGA), and a
same-range leaderboard of every team's totals so a team's numbers can
be shown with a rank, the same way every player-facing page already
does.

Note: like queries/player_stats.py and queries/player_info.py, these
build SQL via f-strings rather than bound parameters. `selected_team`
and `range_filter` only ever come from Streamlit selectboxes populated
from trusted, known values (see pages/Team.py), so this isn't
exploitable today -- flagged in the same spot as the other query files
as worth tightening if this project ever takes free-text input.
"""
import pandas as pd
import streamlit as st

from database import run_query


def _range_filter_sql(range_filter: str, gw_column: str = "gw_id") -> str:
    """Same "which gameweeks does this range include" predicate as
    queries/player_stats.py's private helper of the same name -- kept
    as its own copy here rather than imported cross-module, matching
    how get_best_stats/get_gwk/get_rank_metrics each already carry
    their own copy of this exact logic within player_stats.py itself.
    `range_filter` is one of "All gameweeks", "Last 10 gameweeks" or
    "Last 5 gameweeks".
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
def get_teams() -> pd.DataFrame:
    """Every team's name, for the Team page's selectbox."""
    query = """
    select team_name
    from analytics.teams
    order by team_name
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_team_profile(selected_team: str) -> pd.DataFrame:
    """Identity, league position and colours/badge for one team --
    mirrors queries/player_info.py's get_player_info, joining the same
    analytics.team_misc table Player.py already relies on for a team's
    colours/badge.
    """
    query = f"""
    select
        t.team_name,
        t.team_short_name,
        t.team_table_position,
        tm.tm_primary   as 'primary',
        tm.tm_secondary as 'secondary',
        tm.tm_image     as 'image'
    from analytics.teams t
    left join analytics.team_misc tm on tm.tm_id = t.team_id
    where t.team_name = '{selected_team}'
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_team_results(selected_team: str, range_filter: str) -> pd.DataFrame:
    """One row per played fixture for `selected_team` within
    `range_filter`, most recent first: opponent, venue, score, result
    (W/D/L), and that gameweek's underlying team-level xG/xA/xGA.

    team_gw_stats recovers each team's own match-level xG/xA/xGA the
    same way player_rating.sql's team_gw_attack/team_gw_defence CTEs
    already do: xG/xA are summed across every player who took the pitch
    (each player's own figure is their individual contribution to the
    team total), while xGA is averaged rather than summed since
    analytics.player_stats.pg_xGa is a *shared* per-match value across
    every player from the same team, not a personal one.

    Known limitation, same one already documented on player_rating.sql's
    clean-sheet fix (Round 11) and player_points.sql before it: a double
    gameweek shows as two separate fixture rows here (each with its own
    correct score/opponent), but pg_xG/pg_xA/pg_xGa are already combined
    across both matches at source (the FPL API's own per-gameweek
    aggregate has no per-match split) -- so both rows for a double
    gameweek carry the SAME team_xg/team_xa/team_xga figure, and
    is_double_gw flags exactly this so the page can say so rather than
    implying each match had that number independently. Goalscorers/
    assisters (get_team_contributors below) have the same limitation for
    the same reason.
    """
    query = f"""
    with team_gw_stats as (
        select
            p.p_team as team_id,
            ps.pg_gameweek as gw_id,
            sum(ps.pg_xG) as team_xg,
            sum(ps.pg_xA) as team_xa,
            avg(ps.pg_xGa) as team_xga
        from analytics.player_stats ps
        inner join analytics.players p on p.p_id = ps.pg_id
        where ps.pg_minutes > 0
        group by p.p_team, ps.pg_gameweek
    ),

    team_fixture_counts as (
        select team_id, gw_id, count(*) as fixture_count
        from (
            select f_home_team as team_id, f_gameweek as gw_id
            from analytics.fixtures where f_finished = 1
            union all
            select f_away_team as team_id, f_gameweek as gw_id
            from analytics.fixtures where f_finished = 1
        ) x
        group by team_id, gw_id
    ),

    team_fixture_results as (
        select
            f_home_team as team_id,
            f_gameweek  as gw_id,
            'H'         as venue,
            f_away_team as opponent_id,
            f_home_score as own_score,
            f_away_score as opp_score
        from analytics.fixtures
        where f_finished = 1

        union all

        select
            f_away_team as team_id,
            f_gameweek  as gw_id,
            'A'         as venue,
            f_home_team as opponent_id,
            f_away_score as own_score,
            f_home_score as opp_score
        from analytics.fixtures
        where f_finished = 1
    )

    select
        tr.gw_id,
        tr.venue,
        ot.team_short_name as opponent,
        tr.own_score,
        tr.opp_score,
        case
            when tr.own_score > tr.opp_score then 'W'
            when tr.own_score < tr.opp_score then 'L'
            else 'D'
        end as result,
        coalesce(tgs.team_xg, 0)  as team_xg,
        coalesce(tgs.team_xa, 0)  as team_xa,
        coalesce(tgs.team_xga, 0) as team_xga,
        case when tfc.fixture_count > 1 then 1 else 0 end as is_double_gw
    from team_fixture_results tr
    inner join analytics.teams st on st.team_id = tr.team_id
    left join analytics.teams ot on ot.team_id = tr.opponent_id
    left join team_gw_stats tgs
        on tgs.team_id = tr.team_id and tgs.gw_id = tr.gw_id
    left join team_fixture_counts tfc
        on tfc.team_id = tr.team_id and tfc.gw_id = tr.gw_id
    where st.team_name = '{selected_team}'
      and {_range_filter_sql(range_filter, gw_column='tr.gw_id')}
    order by tr.gw_id desc, tr.venue
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_team_contributors(selected_team: str, range_filter: str) -> pd.DataFrame:
    """Every player from `selected_team` who scored or assisted in a
    gameweek within `range_filter` -- one row per player per gameweek,
    left for pages/Team.py to group into a "Salah (2), Núñez" style
    string per gameweek (kept as a plain rowset here rather than built
    into a single aggregated string in SQL, since SQL Server's ordered
    STRING_AGG syntax isn't something the rest of this project's SQL
    has needed before, and the formatting is simple enough to do in
    pandas the same way Home.py already does its own light grouping).
    """
    query = f"""
    select
        ps.pg_gameweek as gw_id,
        p.p_full_name  as player,
        ps.pg_goals    as goals,
        ps.pg_assists  as assists
    from analytics.player_stats ps
    inner join analytics.players p on p.p_id = ps.pg_id
    inner join analytics.teams t on t.team_id = p.p_team
    where t.team_name = '{selected_team}'
      and (ps.pg_goals > 0 or ps.pg_assists > 0)
      and {_range_filter_sql(range_filter, gw_column='ps.pg_gameweek')}
    order by ps.pg_gameweek desc, ps.pg_goals desc, ps.pg_assists desc
    """
    return run_query(query)


def build_contributor_strings(contributors: pd.DataFrame) -> dict:
    """Turn get_team_contributors' one-row-per-player rowset into
    {gw_id: (goalscorers_str, assisters_str)}, e.g.
    (11: ("Salah (2), Núñez", "Robertson")).

    A count is only shown in parentheses when it's more than 1 (a
    single goal/assist just shows the name on its own), matching how
    FPL's own match-stats display reads.
    """
    result = {}
    if contributors.empty:
        return result

    for gw_id, group in contributors.groupby("gw_id"):
        scorers = group[group["goals"] > 0].sort_values("goals", ascending=False)
        assisters = group[group["assists"] > 0].sort_values("assists", ascending=False)

        def _format(rows, count_col):
            return ", ".join(
                f"{row['player']} ({int(row[count_col])})" if row[count_col] > 1 else row["player"]
                for _, row in rows.iterrows()
            )

        result[int(gw_id)] = (_format(scorers, "goals"), _format(assisters, "assists"))

    return result


@st.cache_data(ttl=600)
def get_team_rank_metrics(selected_team: str, range_filter: str) -> pd.DataFrame:
    """`selected_team`'s totals within `range_filter`, ranked against
    every other team over the same range -- the team-level equivalent
    of queries/player_stats.py's get_rank_metrics, feeding the same
    metric_card component so a team's numbers read with a rank exactly
    the same way a player's do elsewhere in this app.

    Every rank column is a row_number() (one distinct rank per team,
    same convention get_rank_metrics uses for players) rather than a
    dense_rank(), so joint-placed teams still each get their own
    number. form_points_rank ranks by the standard 3/1/0 league-points
    formula computed from these same results, not by any FPL-specific
    figure.
    """
    query = f"""
    with team_gw_stats as (
        select
            p.p_team as team_id,
            ps.pg_gameweek as gw_id,
            sum(ps.pg_xG) as team_xg,
            sum(ps.pg_xA) as team_xa,
            avg(ps.pg_xGa) as team_xga
        from analytics.player_stats ps
        inner join analytics.players p on p.p_id = ps.pg_id
        where ps.pg_minutes > 0
        group by p.p_team, ps.pg_gameweek
    ),

    team_fixture_results as (
        select
            f_home_team as team_id,
            f_gameweek  as gw_id,
            f_home_score as own_score,
            f_away_score as opp_score
        from analytics.fixtures
        where f_finished = 1

        union all

        select
            f_away_team as team_id,
            f_gameweek  as gw_id,
            f_away_score as own_score,
            f_home_score as opp_score
        from analytics.fixtures
        where f_finished = 1
    ),

    team_totals as (
        select
            tr.team_id,
            count(*) as games_played,
            sum(case when tr.own_score > tr.opp_score then 1 else 0 end) as wins,
            sum(case when tr.own_score = tr.opp_score then 1 else 0 end) as draws,
            sum(case when tr.own_score < tr.opp_score then 1 else 0 end) as losses,
            sum(tr.own_score) as goals_scored,
            sum(tr.opp_score) as goals_conceded,
            sum(case when tr.opp_score = 0 then 1 else 0 end) as clean_sheets,
            sum(coalesce(tgs.team_xg, 0))  as total_xg,
            sum(coalesce(tgs.team_xa, 0))  as total_xa,
            sum(coalesce(tgs.team_xga, 0)) as total_xga
        from team_fixture_results tr
        left join team_gw_stats tgs
            on tgs.team_id = tr.team_id and tgs.gw_id = tr.gw_id
        where {_range_filter_sql(range_filter, gw_column='tr.gw_id')}
        group by tr.team_id
    ),

    ranked as (
        select
            t.team_name,
            tt.*,
            row_number() over (order by tt.goals_scored desc)              as goals_scored_rank,
            row_number() over (order by tt.goals_conceded asc)             as goals_conceded_rank,
            row_number() over (order by tt.clean_sheets desc)              as clean_sheets_rank,
            row_number() over (order by tt.total_xg desc)                  as xg_rank,
            row_number() over (order by tt.total_xga asc)                  as xga_rank,
            row_number() over (order by (tt.wins * 3 + tt.draws) desc)     as form_points_rank
        from team_totals tt
        inner join analytics.teams t on t.team_id = tt.team_id
    )

    select *
    from ranked
    where team_name = '{selected_team}'
    """
    return run_query(query)
