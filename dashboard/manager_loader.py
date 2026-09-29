"""On-demand ingestion for the My Team page: fetch any FPL manager from the
API and write them to the warehouse, reusing the extraction pipeline's code
(extraction/managers.py) so there is one way data gets in.

The manager models in dbt are views over the raw tables, so a manager
appears in ``analytics.manager_*`` as soon as this returns.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from database import run_query
from queries.common import PLAYED_GAMEWEEKS_SQL
from queries.manager_data import (
    get_known_managers,
    get_manager_gameweek_history,
    get_manager_profile,
    get_manager_squad,
    get_manager_transfers,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction"))
from db import get_engine as get_write_engine  # noqa: E402
from managers import ManagerNotFound, ingest_manager, parse_manager_id  # noqa: E402

__all__ = ["ManagerNotFound", "load_manager", "parse_manager_id"]


@st.cache_resource
def _engine():
    return get_write_engine()


def _started_gameweeks() -> list[int]:
    gameweeks = run_query(f"select gw_id from analytics.gameweeks where {PLAYED_GAMEWEEKS_SQL} order by gw_id")
    return [int(gw) for gw in gameweeks["gw_id"]] if not gameweeks.empty else []


def load_manager(entry_id: int) -> None:
    """Fetch ``entry_id`` from the FPL API, store it, and clear the cached
    queries so the page shows the fresh data. Raises ManagerNotFound."""
    ingest_manager(_engine(), entry_id, _started_gameweeks())
    for query in (
        get_known_managers,
        get_manager_profile,
        get_manager_squad,
        get_manager_gameweek_history,
        get_manager_transfers,
    ):
        query.clear()
