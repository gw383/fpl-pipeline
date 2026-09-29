"""Shared helpers for the extraction scripts.

* **API access** -- one pooled HTTP session with retries for every call to
  the FPL API (and the Premier League's match API, see pl_events.py).
* **Loading** -- *season-partitioned* tables (players, teams, fixtures,
  gameweeks, live stats) have the current season's rows (or one gameweek's
  rows) deleted and re-inserted in a **single transaction**, so a failed or
  concurrent run can never leave a partition empty or duplicated. Manager
  tables are replaced one manager at a time the same way (see managers.py).

* **Incremental gameweeks** -- deciding which gameweeks' live stats still
  need (re-)fetching.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from urllib3.util.retry import Retry

from config import FPL_API_BASE_URL, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

RAW_SCHEMA = "raw"

# The most recently ingested gameweeks keep being re-fetched for this many
# gameweeks even after FPL marks them ``data_checked``. FPL can still correct
# a finished gameweek's stats for a day or two; this guards against a
# snapshot taken mid-correction (e.g. one match's stats not yet published)
# becoming permanent.
GRACE_GAMEWEEKS = 2


# ---------------------------------------------------------------------------
# FPL API
# ---------------------------------------------------------------------------


def _build_session() -> requests.Session:
    """A pooled session that retries transient failures with backoff.

    404s are deliberately *not* retried -- the API returns them for things
    that legitimately don't exist yet (e.g. picks for a future gameweek).
    """
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


_SESSION = _build_session()


def fetch_url_json(url: str, headers: dict[str, str] | None = None) -> Any:
    """GET any ``url`` on the shared retrying session and decode the JSON body."""
    response = _SESSION.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def fetch_json(path: str) -> Any:
    """GET ``{FPL_API_BASE_URL}/{path}/`` and return the decoded JSON body."""
    return fetch_url_json(f"{FPL_API_BASE_URL}/{path.strip('/')}/")


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------


def utc_now() -> datetime:
    """Current UTC timestamp, used to stamp every load."""
    return datetime.now(UTC)


def convert_nested_to_json(df: pd.DataFrame) -> pd.DataFrame:
    """Serialise any dict/list values in ``df`` to JSON strings.

    SQL Server has no column type for nested structures, so the few nested
    fields the FPL API returns are stored as JSON text.
    """

    def is_nested(value: Any) -> bool:
        return isinstance(value, (dict, list))

    for col in df.columns:
        if df[col].map(is_nested).any():
            df[col] = df[col].map(lambda value: json.dumps(value) if is_nested(value) else value)
    return df


def prepare_for_load(df: pd.DataFrame) -> pd.DataFrame:
    """Stringify ``load_timestamp`` so SQL Server stores it consistently."""
    df = df.copy()
    df["load_timestamp"] = df["load_timestamp"].astype(str)
    return df


# ---------------------------------------------------------------------------
# Loading into the raw schema
# ---------------------------------------------------------------------------


def ensure_raw_schema(engine: Engine) -> None:
    """Create the ``raw`` schema on a fresh database."""
    with engine.begin() as conn:
        conn.execute(text(f"IF SCHEMA_ID('{RAW_SCHEMA}') IS NULL EXEC('CREATE SCHEMA {RAW_SCHEMA}')"))


def table_exists(conn: Connection, table_name: str) -> bool:
    return inspect(conn).has_table(table_name, schema=RAW_SCHEMA)


def replace_partition(
    conn: Connection,
    df: pd.DataFrame,
    table_name: str,
    season: str,
    gameweek: int | None = None,
) -> None:
    """Replace one season's rows (or one season + gameweek's rows) in
    ``raw.<table_name>`` with ``df``.

    Runs on the caller's connection so several tables can share a single
    transaction. The table is created by ``to_sql`` on first load.
    """
    deleted = 0
    if table_exists(conn, table_name):
        where = "season = :season"
        params: dict[str, Any] = {"season": season}
        if gameweek is not None:
            where += " AND event_id = :gameweek"
            params["gameweek"] = gameweek
        deleted = conn.execute(text(f"DELETE FROM {RAW_SCHEMA}.{table_name} WHERE {where}"), params).rowcount

    prepare_for_load(df).to_sql(table_name, conn, schema=RAW_SCHEMA, if_exists="append", index=False)

    scope = f"{season} GW{gameweek}" if gameweek is not None else season
    logger.info("raw.%s [%s]: replaced %s rows with %s", table_name, scope, deleted, len(df))


# ---------------------------------------------------------------------------
# Incremental gameweek selection
# ---------------------------------------------------------------------------


def _gameweeks_needing_fetch(all_gameweeks: list[int], ingested: set[int], checked: dict[int, bool]) -> list[int]:
    """Pure decision logic behind :func:`determine_gameweeks_to_fetch`.

    A gameweek needs fetching if it has never been ingested, if FPL hasn't
    yet marked it ``data_checked`` (a gameweek missing from ``checked`` is
    treated as unchecked), or if it is one of the ``GRACE_GAMEWEEKS`` most
    recently ingested gameweeks. Input order is preserved.
    """
    already_ingested = sorted(gw for gw in all_gameweeks if gw in ingested)
    grace_window = set(already_ingested[-GRACE_GAMEWEEKS:])

    return [gw for gw in all_gameweeks if gw not in ingested or not checked.get(gw, False) or gw in grace_window]


def determine_gameweeks_to_fetch(
    engine: Engine,
    all_gameweeks: list[int],
    season: str,
    table_name: str,
) -> list[int]:
    """Return the subset of ``all_gameweeks`` whose live stats in
    ``raw.<table_name>`` are missing or may still change.

    Settled gameweeks (ingested, ``data_checked`` and outside the grace
    window) are skipped, which turns the live-stats load into an
    incremental one.
    """
    with engine.connect() as conn:
        if not table_exists(conn, table_name):
            return list(all_gameweeks)

        ingested = {
            row[0]
            for row in conn.execute(
                text(f"SELECT DISTINCT event_id FROM {RAW_SCHEMA}.{table_name} WHERE season = :season"),
                {"season": season},
            )
        }
        checked = {
            row[0]: bool(row[1])
            for row in conn.execute(
                text(f"SELECT id, data_checked FROM {RAW_SCHEMA}.raw_gameweeks WHERE season = :season"),
                {"season": season},
            )
        }

    return _gameweeks_needing_fetch(all_gameweeks, ingested, checked)
