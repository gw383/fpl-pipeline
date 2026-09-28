"""Ingests basic profile info for a list of FPL manager entry IDs."""
from __future__ import annotations

import pandas as pd
import requests
from sqlalchemy.engine import Engine

from common import load_table_replace, utc_now

TABLE_NAME = "raw_manager_profiles"


def fetch_entry(entry_id: int) -> dict:
    """Fetch a manager's public entry profile from the FPL API."""
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def manager_profiles(engine: Engine, entry_ids: list[int]) -> None:
    """Ingest profile data for each manager in `entry_ids`."""
    print(f"Ingesting manager profiles ({len(entry_ids)} managers)")

    rows = []
    for entry_id in entry_ids:
        try:
            data = fetch_entry(entry_id)
            rows.append({
                "entry_id": entry_id,
                "player_name": data.get("player_name"),
                "team_name": data.get("name"),
                "overall_points": data.get("summary_overall_points"),
                "overall_rank": data.get("summary_overall_rank"),
                "value": data.get("last_deadline_value"),
                # Added alongside "value" (squad value) for the My Team
                # page -- FPL reports these as two separate figures
                # (squad value + money in the bank), and a manager's true
                # budget is the sum of both, not "value" alone.
                "bank": data.get("last_deadline_bank"),
                "load_timestamp": utc_now(),
            })
            print(f"Loaded manager {entry_id}")
        except Exception as exc:
            print(f"Failed {entry_id}: {exc}")

    df = pd.DataFrame(rows)
    if df.empty:
        return

    load_table_replace(df, TABLE_NAME, engine)
    print("Manager profiles complete")
