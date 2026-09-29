"""Ingest every current player's previous Premier League seasons.

FPL's ``element-summary/<id>`` endpoint has a ``history_past`` list: one row
per past Premier League season with that season's totals (minutes, goals,
xG, xA, BPS, saves, defensive actions, prices...). The projection model uses
it as a prior on each player's ability, so it doesn't start every season
knowing nothing.

Past seasons don't change, so this is a once-a-season load: each player is
fetched once per season and remembered in ``raw_player_history_checked``
(including players with no Premier League history, so they aren't
re-requested every day). Players added mid-season are picked up on the next
run. ``--refetch-history`` reloads everyone.

History totals include penalties, which the model treats as a role rather
than chance creation, so the Premier League match API's goal events are
also loaded for the previous seasons (see pl_events.py); dbt uses them to
count each player's penalties per past season.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from common import RAW_SCHEMA, fetch_json, prepare_for_load, table_exists, utc_now
from config import CURRENT_SEASON

logger = logging.getLogger(__name__)

HISTORY_TABLE = "raw_player_history_past"
CHECKED_TABLE = "raw_player_history_checked"
BATCH_SIZE = 50  # players stored per transaction

# The history_past fields kept (anything missing from the API, e.g. the
# defensive-action columns before 2025-26, is stored as NULL).
HISTORY_FIELDS = {
    "season_name": "NVARCHAR(20)",
    "element_code": "BIGINT",
    "start_cost": "BIGINT",
    "end_cost": "BIGINT",
    "total_points": "BIGINT",
    "minutes": "BIGINT",
    "starts": "BIGINT",
    "goals_scored": "BIGINT",
    "assists": "BIGINT",
    "clean_sheets": "BIGINT",
    "goals_conceded": "BIGINT",
    "own_goals": "BIGINT",
    "penalties_saved": "BIGINT",
    "penalties_missed": "BIGINT",
    "yellow_cards": "BIGINT",
    "red_cards": "BIGINT",
    "saves": "BIGINT",
    "bonus": "BIGINT",
    "bps": "BIGINT",
    "expected_goals": "FLOAT",
    "expected_assists": "FLOAT",
    "expected_goals_conceded": "FLOAT",
    "defensive_contribution": "FLOAT",
    "clearances_blocks_interceptions": "FLOAT",
    "recoveries": "FLOAT",
    "tackles": "FLOAT",
}
TABLE_DDL = {
    HISTORY_TABLE: "player_id BIGINT NOT NULL, "
    + ", ".join(f"{name} {sql_type}" for name, sql_type in HISTORY_FIELDS.items())
    + ", team_join_date NVARCHAR(40), season NVARCHAR(20), load_timestamp NVARCHAR(64)",
    CHECKED_TABLE: "player_id BIGINT NOT NULL, past_seasons BIGINT, season NVARCHAR(20), load_timestamp NVARCHAR(64)",
}
FLOAT_FIELDS = [name for name, sql_type in HISTORY_FIELDS.items() if sql_type == "FLOAT"]

Row = dict[str, Any]


def _number(value: Any) -> float | None:
    """The API sends xG and friends as strings ("3.41")."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_history_past(player: dict[str, Any], summary: dict[str, Any]) -> list[Row]:
    """One row per previous Premier League season for a bootstrap player."""
    rows = []
    for season in summary.get("history_past") or []:
        row: Row = {"player_id": int(player["id"])}
        for name in HISTORY_FIELDS:
            value = season.get(name)
            row[name] = _number(value) if name in FLOAT_FIELDS else value
        row["element_code"] = row["element_code"] or player.get("code")
        row["team_join_date"] = player.get("team_join_date")
        rows.append(row)
    return rows


def ensure_history_tables(engine: Engine) -> None:
    """Create the (empty) raw tables so dbt can build on them before the first load."""
    with engine.begin() as conn:
        for table, columns in TABLE_DDL.items():
            if not table_exists(conn, table):
                conn.execute(text(f"CREATE TABLE {RAW_SCHEMA}.{table} ({columns})"))


def checked_player_ids(engine: Engine, season: str = CURRENT_SEASON) -> set[int]:
    with engine.connect() as conn:
        if not table_exists(conn, CHECKED_TABLE):
            return set()
        query = text(f"SELECT player_id FROM {RAW_SCHEMA}.{CHECKED_TABLE} WHERE season = :season")
        return {int(row[0]) for row in conn.execute(query, {"season": season})}


def _store_batch(engine: Engine, history: list[Row], checked: list[Row]) -> None:
    """Replace these players' rows for the current season in one transaction."""
    ids = sorted({row["player_id"] for row in checked})
    load_time = utc_now()
    with engine.begin() as conn:
        for table in (HISTORY_TABLE, CHECKED_TABLE):
            conn.execute(
                text(
                    f"DELETE FROM {RAW_SCHEMA}.{table} WHERE season = :season "
                    f"AND player_id IN ({', '.join(str(i) for i in ids)})"
                ),
                {"season": CURRENT_SEASON},
            )
        for table, rows in ((HISTORY_TABLE, history), (CHECKED_TABLE, checked)):
            if rows:
                df = pd.DataFrame(rows).assign(season=CURRENT_SEASON, load_timestamp=load_time)
                prepare_for_load(df).to_sql(table, conn, schema=RAW_SCHEMA, if_exists="append", index=False)


def ingest_player_history(engine: Engine, players: Iterable[dict[str, Any]], refetch: bool = False) -> None:
    """Fetch history_past for every bootstrap player not yet loaded this season."""
    ensure_history_tables(engine)
    players = list(players)
    done = set() if refetch else checked_player_ids(engine)
    to_fetch = [p for p in players if int(p["id"]) not in done]
    if not to_fetch:
        logger.info("Player history: every player is already loaded for %s", CURRENT_SEASON)
        return

    logger.info("Player history: fetching %s player(s)", len(to_fetch))
    for start in range(0, len(to_fetch), BATCH_SIZE):
        batch = to_fetch[start : start + BATCH_SIZE]
        history: list[Row] = []
        checked: list[Row] = []
        for player in batch:
            rows = parse_history_past(player, fetch_json(f"element-summary/{player['id']}"))
            history.extend(rows)
            checked.append({"player_id": int(player["id"]), "past_seasons": len(rows)})
        _store_batch(engine, history, checked)
        logger.info("Player history: %s / %s players loaded", start + len(batch), len(to_fetch))
