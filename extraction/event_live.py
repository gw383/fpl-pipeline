"""Ingest per-player, per-gameweek live stats (``event/<gw>/live``)."""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy.engine import Engine

from common import (
    convert_nested_to_json,
    determine_gameweeks_to_fetch,
    fetch_json,
    replace_partition,
    utc_now,
)
from config import CURRENT_SEASON

logger = logging.getLogger(__name__)

TABLE_NAME = "raw_event_live"


def ingest_event_live(engine: Engine, gameweeks: list[int], refetch_all: bool = False) -> None:
    """Load live stats for whichever of ``gameweeks`` still need it.

    By default only new, not-yet-final or recently ingested gameweeks are
    fetched (see ``common.determine_gameweeks_to_fetch``); ``refetch_all``
    reloads every gameweek in ``gameweeks``, e.g. to repair a bad load.
    """
    to_fetch = (
        list(gameweeks) if refetch_all else determine_gameweeks_to_fetch(engine, gameweeks, CURRENT_SEASON, TABLE_NAME)
    )
    if not to_fetch:
        logger.info("Live stats: every gameweek is already up to date")
        return

    logger.info("Live stats: fetching %s of %s gameweeks", len(to_fetch), len(gameweeks))

    for gw in to_fetch:
        elements = fetch_json(f"event/{gw}/live").get("elements", [])
        if not elements:
            logger.info("GW%s has no live stats yet; skipping", gw)
            continue

        df = pd.json_normalize(elements)
        df.columns = [col.lower().replace(" ", "_") for col in df.columns]
        df["event_id"] = gw
        df["season"] = CURRENT_SEASON
        df["load_timestamp"] = utc_now()

        with engine.begin() as conn:
            replace_partition(conn, convert_nested_to_json(df), TABLE_NAME, CURRENT_SEASON, gw)
