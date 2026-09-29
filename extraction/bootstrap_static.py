"""Ingest the FPL ``bootstrap-static`` endpoint.

One response carries four reference datasets -- players, teams, positions
and gameweeks -- each loaded into its own raw table. All four are replaced
in a single transaction so the reference data is always mutually consistent.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy.engine import Engine

from common import convert_nested_to_json, fetch_json, replace_partition, utc_now
from config import CURRENT_SEASON

logger = logging.getLogger(__name__)

# API response key -> raw table.
RAW_TABLES = {
    "elements": "raw_players",
    "teams": "raw_teams",
    "element_types": "raw_positions",
    "events": "raw_gameweeks",
}


def started_gameweeks(events: list[dict[str, Any]], now: datetime | None = None) -> list[int]:
    """IDs of the gameweeks whose deadline has passed, in ascending order.

    Only these have live stats or manager picks to fetch -- requesting a
    future gameweek just returns nothing (or a 404).
    """
    now = now or utc_now()
    return sorted(
        event["id"]
        for event in events
        if event.get("deadline_time") and datetime.fromisoformat(event["deadline_time"].replace("Z", "+00:00")) <= now
    )


def ingest_bootstrap_static(engine: Engine) -> dict[str, Any]:
    """Load players, teams, positions and gameweeks for ``CURRENT_SEASON``.

    Returns the raw API payload so later steps can reuse it (e.g. the
    gameweek list) without a second request.
    """
    data = fetch_json("bootstrap-static")
    load_time = utc_now()

    with engine.begin() as conn:
        for api_key, table_name in RAW_TABLES.items():
            df = pd.DataFrame(data[api_key])
            df["load_timestamp"] = load_time
            df["season"] = CURRENT_SEASON
            replace_partition(conn, convert_nested_to_json(df), table_name, CURRENT_SEASON)

    return data
