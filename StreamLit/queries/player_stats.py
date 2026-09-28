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

    Every rank column is a row_number() -- one distinct rank per player,
    ties on the underlying stat broken by current form -- rather than a
    dense_rank() that gives joint leaders the same number. See the note
    on ranked_players below.
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
                / nullif(max(p_price), 0)                                      as ppm90,
            -- p_form is a scalar per player (FPL's own rolling form
            -- figure), not something to sum across gameweeks -- max()
            -- here is just how SQL Server lets a functionally-dependent
            -- column ride along in a GROUP BY query, same as p_price
            -- above for ppm90. Backs the Player page's "Form" metric
            -- card (see pages/Player.py), which replaced the old
            -- "Value (Points per million per 90)" card.
            max(p_form)                                                        as form_value
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

    -- Round 7.3 note: these used to be dense_rank(), which gives joint
    -- top scorers on a metric the same rank number (e.g. two players
    -- tied on 10 goals both showing "#1", then the next player down
    -- jumping straight to "#2" -- densely packed, no gaps, but not one
    -- rank per player). Switched to row_number(), which always assigns
    -- exactly one distinct rank per player -- ties on the primary stat
    -- are broken by form_value (whoever's in better form right now
    -- ranks above an equally-matched but out-of-form player), and a
    -- final tiebreak on p_full_name keeps the ordering fully
    -- deterministic (so a genuine dead-heat on both stat and form
    -- doesn't produce a different order on every cache refresh).
    -- form_rank's own tiebreak is points rather than form_value again,
    -- since using a metric as its own tiebreak would be meaningless.
    ranked_players as (
        select
            p.*,
            row_number() over (partition by p.p_position order by p.points desc, p.form_value desc, p.p_full_name)     as points_rank,
            row_number() over (partition by p.p_position order by p.goals desc, p.form_value desc, p.p_full_name)      as goals_rank,
            row_number() over (partition by p.p_position order by p.assists desc, p.form_value desc, p.p_full_name)    as assists_rank,
            row_number() over (partition by p.p_position order by p.bonus desc, p.form_value desc, p.p_full_name)      as bonus_rank,
            row_number() over (partition by p.p_position order by p.savesp90 desc, p.form_value desc, p.p_full_name)   as saves_rank,
            row_number() over (partition by p.p_position order by p.saved_pens desc, p.form_value desc, p.p_full_name) as saved_pens_rank,
            row_number() over (partition by p.p_position order by p.cs desc, p.form_value desc, p.p_full_name)         as cs_rank,
            row_number() over (partition by p.p_position order by p.defcons desc, p.form_value desc, p.p_full_name)    as defcons_rank,
            row_number() over (partition by p.p_position order by p.dcp90 desc, p.form_value desc, p.p_full_name)      as dcp90_rank,
            row_number() over (partition by p.p_position order by p.pp90 desc, p.form_value desc, p.p_full_name)       as pp90_rank,
            row_number() over (partition by p.p_position order by p.ppm90_value desc, p.form_value desc, p.p_full_name) as ppm90_rank,
            row_number() over (partition by p.p_position order by p.form_value desc, p.points desc, p.p_full_name)      as form_rank
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

    Reads one row out of analytics.player_rating, a dbt model that is the
    single canonical implementation of this scoring model (see
    transformation/models/analytics/player_rating.sql for the full
    formula, the per-position tunable weights, and the reasoning behind
    each ingredient).

    Round 7 note: the previous version of this query selected five
    ingredients (quality_score, recent_form_score, team_results_score,
    team_strength_score, opponent_difficulty_score) from a model that
    blended season totals against a hard last-5-gameweek window and
    scored team form from match results. player_rating.sql was rewritten
    around a different set of four ingredients -- a single recency-
    weighted quality rate (replacing the season/last-5 split),
    defensive-contribution rate, team underlying attack/defence strength
    (replacing match-results-based team form), and a fixture outlook
    driven by those same underlying team numbers -- so the columns below
    were updated to match.

    Round 7.1 note: also carries each ingredient's actual *_weight for
    this player. These aren't purely a lookup by position any more --
    a midfielder's quality_weight/defcon_weight now depend on their own
    defensive-contribution involvement too (see
    MID_DEFCON_ROLE_THRESHOLD in player_rating.sql) -- so the weight has
    to travel with the row rather than being looked up client-side.
    """
    query = f"""
    select
        player,
        p_position,
        quality_actual_score,
        quality_expected_score,
        quality_score,
        quality_weight,
        defensive_contribution_score,
        defcon_weight,
        team_attack_score,
        team_defence_score,
        team_strength_score,
        team_strength_weight,
        fixture_outlook_score,
        fixtures_weight,
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

    Position-by-position top 5s (rather than one flat top-20 across every
    position) are a more honest read of "who's the best pick at each
    position right now" -- comparing goalkeepers against forwards on the
    same list isn't a fair comparison.

    Also carries the 4 weighted ingredients behind `star` (plus each
    ingredient's actual weight for that player, and the minutes-security
    gate) so the "Top rated players" cards can expand to show how each
    rating was actually reached, not just the number itself -- see
    components/rating_breakdown.py.
    """
    query = """
    with ranked as (
        select
            p_id,
            player,
            p_position,
            star as rating,
            quality_score,
            quality_weight,
            defensive_contribution_score,
            defcon_weight,
            team_strength_score,
            team_strength_weight,
            fixture_outlook_score,
            fixtures_weight,
            minutes_security_score,
            row_number() over (partition by p_position order by star desc) as position_rank
        from analytics.player_rating
    )
    select
        p_id,
        player,
        p_position,
        rating,
        quality_score,
        quality_weight,
        defensive_contribution_score,
        defcon_weight,
        team_strength_score,
        team_strength_weight,
        fixture_outlook_score,
        fixtures_weight,
        minutes_security_score
    from ranked
    where position_rank <= 5
    order by p_position, position_rank
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_star_by_position(position: int, limit: int = 30) -> pd.DataFrame:
    """The full "star" leaderboard for ONE position, not capped at 5 --
    for the Rankings page's bigger list ("so I can see a bigger list of
    who is good at the moment and who isn't"). get_star_top5_by_position
    stays exactly as it was for the Home page's compact top-5-per-
    position section; this is the same idea with the cap raised (or
    lifted -- pass a large `limit` for "show everyone").

    `position` is 1/2/3/4 (GKP/DEF/MID/FWD), matching analytics.players.
    p_position and every other position column in this project. Carries
    the same ingredients/weights as get_star_top5_by_position so each
    row can expand to the same rating-breakdown panel.
    """
    query = f"""
    select top ({limit})
        p_id,
        player,
        p_position,
        star as rating,
        quality_score,
        quality_weight,
        defensive_contribution_score,
        defcon_weight,
        team_strength_score,
        team_strength_weight,
        fixture_outlook_score,
        fixtures_weight,
        minutes_security_score
    from analytics.player_rating
    where p_position = {position}
    order by star desc
    """
    return run_query(query)


@st.cache_data(ttl=600)
def get_in_form_differentials(max_ownership: float = 10.0, limit: int = 20) -> pd.DataFrame:
    """Low-ownership players currently in good recent form -- candidates
    worth a look as differentials, for the Home page.

    "In form" here is quality_score specifically (analytics.player_rating's
    recency-weighted blend of actual/expected points per 90 -- see the
    player_rating.sql rewrite notes on why this replaced the old model's
    separate last-5-gameweek "recent_form_score" bucket: quality_score IS
    now the recency-aware "how well is this player playing lately" signal,
    just computed as a smooth decay rather than a hard 5-gameweek window),
    not the overall star rating -- star also folds in fixture outlook and
    team strength, which would drown out "is this player playing well
    right now" with "are their next few fixtures favourable". minutes_
    security_score is still used as a floor filter (not just a display
    value) so a one-off cameo goal doesn't show up here as a nailed-on
    differential.

    Round 7.1 note: these cards no longer expand to a breakdown (removed
    per feedback -- the differentials list is meant to be a quick scan,
    and the breakdown toggle was adding a lot of visual noise across 20
    cards at once). So this only selects what differential_card.py
    itself displays plus the two columns the query logic depends on
    (quality_score to order by, minutes_security_score to filter on) --
    trimmed from the previous version, which also carried
    defensive_contribution_score/team_strength_score/fixture_outlook_score/
    star purely to feed a breakdown panel that no longer exists here.
    """
    query = f"""
    select top ({limit})
        pr.p_id,
        pr.player,
        pr.p_position,
        pl.p_ownership     as ownership,
        pl.p_price          as price,
        pr.quality_score
    from analytics.player_rating pr
    left join analytics.players pl on pl.p_id = pr.p_id
    where pl.p_ownership <= {max_ownership}
      and pr.minutes_security_score >= 0.5
    order by pr.quality_score desc
    """
    return run_query(query)
