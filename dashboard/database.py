"""SQL Server access for the dashboard.

Connection settings are the pipeline's (``extraction/db.py``): ``FPL_DB_*``
environment variables, from ``.env`` locally or the app's secrets when
hosted. A local SQL Server can use Windows authentication; the hosted app
uses a SQL login and the pymssql driver (``FPL_DB_DRIVER=pymssql``).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

import runtime_env  # noqa: F401  -- secrets -> environment, before the settings are read

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction"))
from db import get_engine as build_engine  # noqa: E402

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


@st.cache_resource
def get_engine() -> Engine:
    """One pooled engine per Streamlit server process."""
    return build_engine()


def run_query(query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run a parameterised query (``:name`` placeholders) and return a DataFrame.

    If the database is still waking up, it waits and retries. Other database
    errors are shown as a banner and an empty DataFrame is returned, so each
    page's own "no data" handling takes over instead of a traceback.
    """
    for attempt in range(1, WAKE_ATTEMPTS + 1):
        try:
            with get_engine().connect() as conn:
                return pd.read_sql(text(query), conn, params=params or {})
        except DBAPIError as exc:
            if attempt == WAKE_ATTEMPTS or not is_waking_up(exc):
                st.error(f"Couldn't load data from the database: {exc}")
                return pd.DataFrame()
            with st.spinner("Waking up the database, this can take up to a minute..."):
                time.sleep(WAKE_DELAY_SECONDS)
        except SQLAlchemyError as exc:
            st.error(f"Couldn't load data from the database: {exc}")
            return pd.DataFrame()
    return pd.DataFrame()
