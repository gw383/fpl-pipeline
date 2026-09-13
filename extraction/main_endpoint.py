"""Ingests the FPL "bootstrap-static" endpoint.

This single endpoint returns four reference datasets in one response:
players, teams, positions and gameweeks. Each is loaded into its own
raw table, replacing only the current season's rows.
"""
from __future__ import annotations

import pandas as pd
import requests
from sqlalchemy.engine import Engine

from common import convert_nested_to_json, delete_season_data, load_table_append, utc_now
from config import CURRENT_SEASON

BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

# Maps each key in the API response to the raw table it is loaded into.
RAW_TABLES = {
    "elements": "raw_players",
    "teams": "raw_teams",
    "element_types": "raw_positions",
    "events": "raw_gameweeks",
}


def fetch_bootstrap_data() -> dict:
    """Fetch the raw bootstrap-static payload from the FPL API."""
    response = requests.get(BOOTSTRAP_URL, timeout=30)
    response.raise_for_status()
    return response.json()


def main_endpoint(engine: Engine) -> None:
    """Ingest players, teams, positions and gameweeks for CURRENT_SEASON."""
    print("Starting bootstrap-static ingestion...")

    data = fetch_bootstrap_data()
    load_time = utc_now()

    frames = {}
    for api_key, table_name in RAW_TABLES.items():
        df = pd.DataFrame(data[api_key])
        df["load_timestamp"] = load_time
        df["season"] = CURRENT_SEASON
        frames[table_name] = convert_nested_to_json(df)

    for table_name in RAW_TABLES.values():
        delete_season_data(engine, table_name, CURRENT_SEASON)

    for table_name, df in frames.items():
        load_table_append(df, table_name, engine)

    print("Bootstrap-static ingestion complete")
