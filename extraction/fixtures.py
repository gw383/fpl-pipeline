"""Ingests fixture data (kickoff times, scores, difficulty) from the FPL API."""
from __future__ import annotations

import pandas as pd
import requests
from sqlalchemy.engine import Engine

from common import delete_season_data, load_table_append, utc_now
from config import CURRENT_SEASON

FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"
TABLE_NAME = "raw_fixtures"


def fetch_fixtures() -> list[dict]:
    """Fetch the full fixture list for the current season from the FPL API."""
    response = requests.get(FIXTURES_URL, timeout=30)
    response.raise_for_status()
    return response.json()


def fixtures(engine: Engine) -> None:
    """Ingest fixtures for CURRENT_SEASON, replacing any existing rows."""
    print("Starting fixtures ingestion...")

    data = pd.DataFrame(fetch_fixtures())

    if data.empty:
        print("No fixture data returned")
        return

    data.columns = [col.lower().replace(" ", "_") for col in data.columns]
    data["load_timestamp"] = utc_now()
    data["season"] = CURRENT_SEASON

    delete_season_data(engine, TABLE_NAME, CURRENT_SEASON)
    load_table_append(data, TABLE_NAME, engine)

    print("Fixtures ingestion complete")
