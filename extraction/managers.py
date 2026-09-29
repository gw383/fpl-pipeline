"""Ingest FPL manager data: profile, gameweek picks (with each gameweek's
points/rank/budget summary) and transfer history.

Managers are loaded **one at a time**: all of a manager's rows are fetched
first, then that manager's rows in the four raw tables are replaced in a
single transaction. That lets the dashboard pull in any manager on demand
without touching anyone else's data, and a failed fetch never leaves a
manager half-loaded.

The daily pipeline refreshes every manager already in the warehouse plus
those listed in ``FPL_ENTRY_IDS``, so a manager looked up once in the
dashboard stays up to date from then on.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import requests
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from common import RAW_SCHEMA, fetch_json, prepare_for_load, table_exists, utc_now

logger = logging.getLogger(__name__)

PROFILES_TABLE = "raw_manager_profiles"
PICKS_TABLE = "raw_manager_picks"
HISTORY_TABLE = "raw_manager_gameweek_history"
TRANSFERS_TABLE = "raw_manager_transfers"

# Explicit column types, so the tables exist (and dbt can build on them)
# before the first manager is loaded.
TABLE_DDL = {
    PROFILES_TABLE: """
        entry_id BIGINT NOT NULL, player_name NVARCHAR(200), team_name NVARCHAR(200),
        overall_points BIGINT, overall_rank BIGINT, value BIGINT, bank BIGINT,
        load_timestamp NVARCHAR(64)
    """,
    PICKS_TABLE: """
        entry_id BIGINT NOT NULL, event_id BIGINT, player_id BIGINT, multiplier BIGINT,
        is_captain BIT, is_vice_captain BIT, position BIGINT, load_timestamp NVARCHAR(64)
    """,
    HISTORY_TABLE: """
        entry_id BIGINT NOT NULL, event_id BIGINT, points BIGINT, total_points BIGINT,
        overall_rank BIGINT, bank BIGINT, value BIGINT, event_transfers BIGINT,
        event_transfers_cost BIGINT, points_on_bench BIGINT, active_chip NVARCHAR(50),
        load_timestamp NVARCHAR(64)
    """,
    TRANSFERS_TABLE: """
        entry_id BIGINT NOT NULL, element_in BIGINT, element_out BIGINT, event BIGINT,
        [time] NVARCHAR(64), load_timestamp NVARCHAR(64)
    """,
}

Row = dict[str, Any]


class ManagerNotFound(LookupError):
    """The FPL API has no manager with this ID."""


@dataclass
class ManagerData:
    """Every raw row for one manager, ready to store."""

    entry_id: int
    profile: list[Row] = field(default_factory=list)
    picks: list[Row] = field(default_factory=list)
    history: list[Row] = field(default_factory=list)
    transfers: list[Row] = field(default_factory=list)

    def tables(self) -> dict[str, list[Row]]:
        return {
            PROFILES_TABLE: self.profile,
            PICKS_TABLE: self.picks,
            HISTORY_TABLE: self.history,
            TRANSFERS_TABLE: self.transfers,
        }


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# FPL IDs are positive integers; anything longer than this is a typo.
MAX_ID_DIGITS = 10


def parse_manager_id(value: str | int | None) -> int | None:
    """A manager ID from user input (surrounding whitespace allowed), or None
    if it isn't a plausible FPL ID."""
    text = str(value).strip() if value is not None else ""
    if not text.isdigit() or len(text) > MAX_ID_DIGITS or int(text) <= 0:
        return None
    return int(text)


def parse_profile(entry_id: int, data: dict[str, Any]) -> Row:
    """One ``entry/<id>`` response as a profile row."""
    return {
        "entry_id": entry_id,
        # The entry endpoint splits the manager's name into two fields.
        "player_name": " ".join(part for part in (data.get("player_first_name"), data.get("player_last_name")) if part)
        or None,
        "team_name": data.get("name"),
        "overall_points": data.get("summary_overall_points"),
        "overall_rank": data.get("summary_overall_rank"),
        "value": data.get("last_deadline_value"),
        "bank": data.get("last_deadline_bank"),
        "load_timestamp": utc_now(),
    }


def parse_picks(entry_id: int, gw: int, data: dict[str, Any]) -> tuple[list[Row], Row | None]:
    """Split one ``entry/<id>/event/<gw>/picks`` response into pick rows and
    an optional gameweek-summary row."""
    loaded_at = utc_now()
    picks = [
        {
            "entry_id": entry_id,
            "event_id": gw,
            "player_id": pick["element"],
            "multiplier": pick["multiplier"],
            "is_captain": pick["is_captain"],
            "is_vice_captain": pick["is_vice_captain"],
            "position": pick["position"],
            "load_timestamp": loaded_at,
        }
        for pick in data.get("picks", [])
    ]

    summary = data.get("entry_history") or {}
    history = (
        {
            "entry_id": entry_id,
            "event_id": gw,
            "points": summary.get("points"),
            "total_points": summary.get("total_points"),
            "overall_rank": summary.get("overall_rank"),
            "bank": summary.get("bank"),
            "value": summary.get("value"),
            "event_transfers": summary.get("event_transfers"),
            "event_transfers_cost": summary.get("event_transfers_cost"),
            "points_on_bench": summary.get("points_on_bench"),
            "active_chip": data.get("active_chip"),
            "load_timestamp": loaded_at,
        }
        if summary
        else None
    )
    return picks, history


def parse_transfers(entry_id: int, data: list[dict[str, Any]]) -> list[Row]:
    """One ``entry/<id>/transfers`` response as transfer rows."""
    loaded_at = utc_now()
    return [
        {
            "entry_id": entry_id,
            "element_in": transfer["element_in"],
            "element_out": transfer["element_out"],
            "event": transfer["event"],
            "time": transfer["time"],
            "load_timestamp": loaded_at,
        }
        for transfer in data
    ]


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def fetch_manager(entry_id: int, gameweeks: Iterable[int]) -> ManagerData:
    """Fetch one manager's profile, picks for every started gameweek (which
    also carry that gameweek's summary) and transfers.

    Raises :class:`ManagerNotFound` if FPL has no such manager. A gameweek
    with no picks (e.g. the team was created after that deadline) is skipped.
    FPL only publishes a gameweek's picks once its deadline has passed, so
    ``gameweeks`` should contain started gameweeks only.
    """
    try:
        profile = fetch_json(f"entry/{entry_id}")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise ManagerNotFound(f"No FPL manager with ID {entry_id}") from exc
        raise

    manager = ManagerData(entry_id, profile=[parse_profile(entry_id, profile)])
    for gw in gameweeks:
        try:
            data = fetch_json(f"entry/{entry_id}/event/{gw}/picks")
        except requests.HTTPError as exc:
            logger.info("Manager %s: no picks for GW%s (%s)", entry_id, gw, exc)
            continue
        gw_picks, gw_history = parse_picks(entry_id, gw, data)
        manager.picks.extend(gw_picks)
        if gw_history:
            manager.history.append(gw_history)

    manager.transfers = parse_transfers(entry_id, fetch_json(f"entry/{entry_id}/transfers"))
    return manager


# ---------------------------------------------------------------------------
# Storing
# ---------------------------------------------------------------------------


def ensure_manager_tables(engine: Engine) -> None:
    """Create any missing raw manager tables (empty)."""
    with engine.begin() as conn:
        for table, columns in TABLE_DDL.items():
            if not table_exists(conn, table):
                conn.execute(text(f"CREATE TABLE {RAW_SCHEMA}.{table} ({columns})"))
                logger.info("Created raw.%s", table)


def _replace_manager_rows(conn: Connection, manager: ManagerData) -> None:
    for table, rows in manager.tables().items():
        conn.execute(
            text(f"DELETE FROM {RAW_SCHEMA}.{table} WHERE entry_id = :entry_id"), {"entry_id": manager.entry_id}
        )
        if rows:
            prepare_for_load(pd.DataFrame(rows)).to_sql(table, conn, schema=RAW_SCHEMA, if_exists="append", index=False)


def store_managers(engine: Engine, managers: list[ManagerData]) -> None:
    """Replace each manager's rows in all four raw tables, in one transaction."""
    if not managers:
        return
    ensure_manager_tables(engine)
    with engine.begin() as conn:
        for manager in managers:
            _replace_manager_rows(conn, manager)
    logger.info("Stored %d manager(s): %s", len(managers), ", ".join(str(m.entry_id) for m in managers))


def known_manager_ids(engine: Engine) -> list[int]:
    """Every manager already in the warehouse."""
    with engine.connect() as conn:
        if not table_exists(conn, PROFILES_TABLE):
            return []
        rows = conn.execute(text(f"SELECT DISTINCT entry_id FROM {RAW_SCHEMA}.{PROFILES_TABLE}"))
        return sorted(int(row[0]) for row in rows)


def ingest_manager(engine: Engine, entry_id: int, gameweeks: Iterable[int]) -> ManagerData:
    """Fetch and store a single manager (used by the dashboard's My Team
    page). Raises :class:`ManagerNotFound` for an unknown ID."""
    manager = fetch_manager(entry_id, list(gameweeks))
    store_managers(engine, [manager])
    return manager


def ingest_managers(engine: Engine, entry_ids: Iterable[int], gameweeks: Iterable[int]) -> None:
    """Refresh several managers (the daily pipeline). A manager that fails
    to fetch is logged and keeps its previous data."""
    gameweeks = list(gameweeks)
    fetched = []
    for entry_id in entry_ids:
        try:
            fetched.append(fetch_manager(entry_id, gameweeks))
        except Exception as exc:  # one bad manager shouldn't stop the load
            logger.warning("Manager %s: skipped (%s)", entry_id, exc)
    store_managers(engine, fetched)
