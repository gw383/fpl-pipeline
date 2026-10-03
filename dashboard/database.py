"""Data access for the dashboard.

Pages are answered from the dashboard's data file: a SQLite copy of the
warehouse's analytics tables that the pipeline exports after every run
(``serving/``; ``data_source.py`` finds or downloads it). ``run_query`` reads
it, so a page view never waits on SQL Server.

The warehouse itself is only used by the My Team page, for a manager who
isn't in the data file yet (``run_live_query``): one looked up since the
last pipeline run. Its connection settings are the pipeline's
(``extraction/db.py``): ``FPL_DB_*`` from ``.env`` locally or the app's
secrets when hosted.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

import data_source
import runtime_env  # noqa: F401  -- secrets -> environment, before the settings are read
from data_source import DataFile, DataUnavailable
from settings import DATA_REFRESH_SECONDS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "serving"))
import data_file as serving  # noqa: E402
from db import get_engine as build_engine  # noqa: E402

__all__ = [
    "DataUnavailable",
    "current_data",
    "get_engine",
    "live_database_configured",
    "run_live_query",
    "run_query",
    "table_exists",
]

# ---------------------------------------------------------------------------
# The data file
# ---------------------------------------------------------------------------


@st.cache_resource(ttl=DATA_REFRESH_SECONDS, show_spinner="Loading the latest data...")
def _download(url: str) -> DataFile:
    return data_source.download(url)


_served_version: str | None = None
_version_lock = threading.Lock()


def current_data() -> DataFile:
    """The data file in use. A local file is checked every time (it's cheap),
    a downloaded one every ``DATA_REFRESH_SECONDS``. When it has changed,
    every cached query result is dropped so pages show the new data. Raises
    DataUnavailable if there is no usable file."""
    global _served_version
    kind, location = data_source.configured_source()
    data = data_source.load_file(Path(location)) if kind == "file" else _download(location)
    with _version_lock:
        if _served_version is not None and data.version != _served_version:
            st.cache_data.clear()
        _served_version = data.version
    return data


def _plain(value: Any) -> Any:
    """SQLite binds Python values, not NumPy ones (IDs taken from a DataFrame)."""
    return value.item() if hasattr(value, "item") else value


def run_query(query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run a parameterised query (``:name`` placeholders) against the data
    file and return a DataFrame. Tables are addressed as ``analytics.<name>``.

    A query error is shown as a banner and an empty DataFrame is returned,
    so each page's own "no data" handling takes over instead of a traceback.
    """
    data = current_data()
    try:
        conn = serving.connect(data.path)
        try:
            return pd.read_sql_query(query, conn, params={k: _plain(v) for k, v in (params or {}).items()})
        finally:
            conn.close()
    except (sqlite3.Error, pd.errors.DatabaseError, FileNotFoundError) as exc:
        st.error(f"Couldn't read the dashboard's data: {exc}")
        return pd.DataFrame()


def table_exists(table: str) -> bool:
    """Whether the data file has ``table`` (older files lack newer tables)."""
    try:
        conn = serving.connect(current_data().path)
        try:
            return serving.has_table(conn, table)
        finally:
            conn.close()
    except (sqlite3.Error, FileNotFoundError):
        return False


# ---------------------------------------------------------------------------
# The warehouse (My Team lookups only)
# ---------------------------------------------------------------------------

# A paused Azure SQL free-tier database takes up to a minute to wake up.
WAKE_ATTEMPTS = 4
WAKE_DELAY_SECONDS = 15

# Errors that mean "try again shortly" rather than "something is wrong":
# Azure SQL's database-unavailable/resuming codes and connection timeouts.
_WAKING_MARKERS = ("40613", "40197", "40501", "49918", "timeout", "timed out", "unable to connect",
                   "communication link failure", "adaptive server connection failed")  # fmt: skip


def is_waking_up(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _WAKING_MARKERS)


def live_database_configured(environ: dict[str, str] | None = None) -> bool:
    """Whether this copy of the dashboard has a warehouse to look managers up
    in. A dashboard running from the published data file alone doesn't."""
    env = os.environ if environ is None else environ
    return bool(env.get("FPL_DB_SERVER"))


@st.cache_resource
def get_engine() -> Engine:
    """The warehouse engine. Unpooled: an open connection counts as activity
    and would stop a serverless database pausing."""
    return build_engine(pooled=False)


def run_live_query(query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Like ``run_query`` but against the warehouse. If the database is still
    waking up, it waits and retries."""
    params = {k: _plain(v) for k, v in (params or {}).items()}
    for attempt in range(1, WAKE_ATTEMPTS + 1):
        try:
            with get_engine().connect() as conn:
                return pd.read_sql(text(query), conn, params=params)
        except DBAPIError as exc:
            if attempt == WAKE_ATTEMPTS or not is_waking_up(exc):
                st.error(f"Couldn't load data from the database: {exc}")
                return pd.DataFrame()
            with st.spinner("Waking up the database, this can take up to a minute..."):
                time.sleep(WAKE_DELAY_SECONDS)
        except (SQLAlchemyError, ImportError) as exc:  # ImportError: the database driver isn't installed
            st.error(f"Couldn't load data from the database: {exc}")
            return pd.DataFrame()
    return pd.DataFrame()
