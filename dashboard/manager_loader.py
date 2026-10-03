"""On-demand ingestion for the My Team page: fetch any FPL manager from the
API and write them to the warehouse, reusing the extraction pipeline's code
(extraction/managers.py) so there is one way data gets in.

The manager models in dbt are views over the raw tables, so a manager
appears in the warehouse's ``analytics.manager_*`` as soon as this returns.
They reach the dashboard's data file with the next pipeline run; until then
the My Team page reads them from the warehouse (``live=True`` in
queries/manager_data.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from database import get_engine, run_query
from queries.common import PLAYED_GAMEWEEKS_SQL
from queries.manager_data import (
    get_known_managers,
    get_manager_gameweek_history,
    get_manager_profile,
    get_manager_squad,
    get_manager_transfers,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction"))
from managers import ManagerNotFound, ingest_manager, parse_manager_id  # noqa: E402

__all__ = ["ManagerNotFound", "is_live", "load_manager", "mark_live", "parse_manager_id"]

_LIVE_KEY = "live_managers"


def is_live(entry_id: int) -> bool:
    """Whether this session should read ``entry_id`` from the warehouse: they
    were fetched or refreshed in it, so the data file doesn't have them yet
    (or has an older copy)."""
    return int(entry_id) in st.session_state.get(_LIVE_KEY, set())


def mark_live(entry_id: int) -> None:
    st.session_state.setdefault(_LIVE_KEY, set()).add(int(entry_id))


def _started_gameweeks() -> list[int]:
    gameweeks = run_query(f"select gw_id from analytics.gameweeks where {PLAYED_GAMEWEEKS_SQL} order by gw_id")
    return [int(gw) for gw in gameweeks["gw_id"]] if not gameweeks.empty else []


def load_manager(entry_id: int) -> None:
    """Fetch ``entry_id`` from the FPL API, store it in the warehouse, and
    clear the cached queries so the page shows the fresh data (read from the
    warehouse for the rest of this session). Raises ManagerNotFound."""
    ingest_manager(get_engine(), entry_id, _started_gameweeks())
    mark_live(entry_id)
    for query in (
        get_known_managers,
        get_manager_profile,
        get_manager_squad,
        get_manager_gameweek_history,
        get_manager_transfers,
    ):
        query.clear()
