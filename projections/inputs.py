"""Read the model's inputs from the analytics schema and write its outputs
back. The only module in projections/ that touches the database."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from model import ModelInputs, Projection

# Reuse the extraction pipeline's connection settings (FPL_DB_* variables).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction"))
from config import CURRENT_SEASON  # noqa: E402
from db import get_engine  # noqa: E402

logger = logging.getLogger(__name__)

SCHEMA = "analytics"

QUERIES = {
    "players": """
        select p_id, p_web_name, p_full_name, p_team, p_position, p_price, p_start_price,
               p_status, p_chance_of_playing, p_news, p_penalties_order
        from analytics.players
    """,
    "fixtures": """
        select f_id, f_gameweek, f_home_team, f_away_team
        from analytics.fixtures
    """,
    "gameweeks": """
        select gw_id, gw_deadline_time
        from analytics.gameweeks
    """,
    "stats": """
        select pg_id, pg_gameweek, pg_minutes, pg_starts, pg_xG, pg_xA, pg_defcons,
               pg_saves, pg_bonus, pg_yellow_cards, pg_points, pg_bps, pg_goals,
               pg_assists, pg_clean_sheets, pg_goals_conceded, pg_pens_missed
        from analytics.player_stats
    """,
}


PENALTIES_QUERY = """
    select p_id, gw_id, penalties_taken
    from analytics.player_penalties
"""
# Penalty data is only trusted once the Premier League goal events have
# loaded for this season (otherwise player_penalties only has misses).
PENALTY_SOURCE_QUERY = "select count(*) from raw.raw_pl_goal_events where season = :season"


def _load_penalties(conn) -> pd.DataFrame | None:
    """Penalties taken per player-gameweek, or None if the Premier League
    goal events aren't available (the model then skips the penalty split)."""
    try:
        loaded = conn.execute(text(PENALTY_SOURCE_QUERY), {"season": CURRENT_SEASON}).scalar()
        if not loaded:
            logger.warning("No Premier League goal events loaded; projecting without the penalty split")
            return None
        penalties = pd.read_sql(text(PENALTIES_QUERY), conn)
    except SQLAlchemyError as exc:
        logger.warning("Penalty data unavailable (%s); projecting without the penalty split", exc)
        return None
    penalties.columns = [c.lower() for c in penalties.columns]
    return penalties


HISTORY_QUERY = "select * from analytics.player_past_seasons"


def _load_history(conn) -> pd.DataFrame | None:
    """Players' previous seasons, or None if they haven't been loaded (the
    model then uses price-only priors)."""
    try:
        history = pd.read_sql(text(HISTORY_QUERY), conn)
    except SQLAlchemyError as exc:
        logger.warning("Player history unavailable (%s); projecting with price-only priors", exc)
        return None
    if history.empty:
        logger.warning("No player history loaded; projecting with price-only priors")
        return None
    history.columns = [c.lower() for c in history.columns]
    return history


def load_inputs(engine: Engine | None = None) -> ModelInputs:
    """The analytics tables the model reads, with lower-case columns."""
    engine = engine or get_engine()
    with engine.connect() as conn:
        frames = {name: pd.read_sql(text(sql), conn) for name, sql in QUERIES.items()}
        frames["penalties"] = _load_penalties(conn)
        frames["history"] = _load_history(conn)
    for name in QUERIES:
        frames[name].columns = [c.lower() for c in frames[name].columns]
    stats = frames["stats"]
    numeric = [c for c in stats.columns if c.startswith("pg_")]
    stats[numeric] = stats[numeric].apply(pd.to_numeric, errors="coerce").fillna(0)
    players = frames["players"]
    for column in ("p_chance_of_playing", "p_penalties_order", "p_price", "p_start_price"):
        players[column] = pd.to_numeric(players[column], errors="coerce")
    return ModelInputs(**frames)


EXPECTED_TABLE = "player_gameweek_expected"


def load_expected_gameweeks(engine: Engine | None = None) -> set[int]:
    """Gameweeks already in analytics.player_gameweek_expected."""
    engine = engine or get_engine()
    with engine.connect() as conn:
        if not inspect(conn).has_table(EXPECTED_TABLE, schema=SCHEMA):
            return set()
        rows = conn.execute(text(f"select distinct gw from {SCHEMA}.{EXPECTED_TABLE}"))
        return {int(row[0]) for row in rows}


def write_gameweek_expectations(frame: pd.DataFrame, engine: Engine | None = None) -> None:
    """Replace these gameweeks' rows in analytics.player_gameweek_expected
    (created on first use), in one transaction."""
    if frame.empty:
        return
    engine = engine or get_engine()
    gameweeks = sorted({int(gw) for gw in frame["gw"]})
    with engine.begin() as conn:
        if inspect(conn).has_table(EXPECTED_TABLE, schema=SCHEMA):
            conn.execute(
                text(f"delete from {SCHEMA}.{EXPECTED_TABLE} where gw in ({', '.join(str(gw) for gw in gameweeks)})")
            )
        frame.to_sql(EXPECTED_TABLE, conn, schema=SCHEMA, index=False, if_exists="append", chunksize=1000)
    logger.info("Wrote expected points for gameweek(s) %s", gameweeks)


def _replace_table(conn, df: pd.DataFrame, table: str) -> None:
    """Drop ``analytics.<table>`` (table or view) and recreate it from ``df``."""
    conn.execute(text(f"IF OBJECT_ID('{SCHEMA}.{table}', 'V') IS NOT NULL DROP VIEW {SCHEMA}.{table}"))
    conn.execute(text(f"IF OBJECT_ID('{SCHEMA}.{table}', 'U') IS NOT NULL DROP TABLE {SCHEMA}.{table}"))
    df.to_sql(table, conn, schema=SCHEMA, index=False, chunksize=1000)


def write_projection(projection: Projection, players: pd.DataFrame, engine: Engine | None = None) -> None:
    """Replace analytics.player_rating, analytics.player_projection and
    analytics.team_rating in one transaction, so the dashboard never sees a
    half-written set."""
    engine = engine or get_engine()
    run_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    names = players.set_index("p_id")["p_full_name"]
    rating = projection.players.assign(
        player=lambda df: df["p_id"].map(names), as_of_gw=projection.as_of_gw, model_run_at=run_at
    )
    fixtures = projection.fixtures.assign(is_home=projection.fixtures["is_home"].astype(int))
    teams = projection.teams.assign(as_of_gw=projection.as_of_gw, model_run_at=run_at)

    with engine.begin() as conn:
        _replace_table(conn, rating, "player_rating")
        _replace_table(conn, fixtures, "player_projection")
        _replace_table(conn, teams, "team_rating")
    logger.info(
        "Wrote %d player ratings, %d player-fixture projections and %d team ratings (from gameweek %d)",
        len(rating),
        len(fixtures),
        len(teams),
        projection.as_of_gw,
    )
