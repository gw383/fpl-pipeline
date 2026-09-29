"""Ingest the season's fixture list (kick-off times, scores, difficulty)."""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy.engine import Engine

from common import convert_nested_to_json, fetch_json, replace_partition, utc_now
from config import CURRENT_SEASON

logger = logging.getLogger(__name__)

TABLE_NAME = "raw_fixtures"


def ingest_fixtures(engine: Engine) -> None:
    """Replace ``CURRENT_SEASON``'s fixtures with a fresh pull."""
    df = pd.DataFrame(fetch_json("fixtures"))
    if df.empty:
        logger.warning("Fixtures endpoint returned no data; skipping")
        return

    df.columns = [col.lower().replace(" ", "_") for col in df.columns]
    df["load_timestamp"] = utc_now()
    df["season"] = CURRENT_SEASON

    with engine.begin() as conn:
        replace_partition(conn, convert_nested_to_json(df), TABLE_NAME, CURRENT_SEASON)
