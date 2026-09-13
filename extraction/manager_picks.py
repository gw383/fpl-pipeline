"""Ingests each manager's gameweek-by-gameweek picks."""
from __future__ import annotations

import pandas as pd
import requests
from sqlalchemy.engine import Engine

from common import load_table_replace, utc_now

TABLE_NAME = "raw_manager_picks"


def fetch_picks(entry_id: int, gameweek: int) -> dict:
    """Fetch one manager's picks for a single gameweek."""
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gameweek}/picks/"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def manager_picks(engine: Engine, entry_ids: list[int], gameweeks: list[int]) -> None:
    """Ingest picks for every (manager, gameweek) combination."""
    print("Ingesting manager picks")

    rows = []
    for entry_id in entry_ids:
        for gw in gameweeks:
            try:
                data = fetch_picks(entry_id, gw)
                for pick in data.get("picks", []):
                    rows.append({
                        "entry_id": entry_id,
                        "event_id": gw,
                        "player_id": pick["element"],
                        "multiplier": pick["multiplier"],
                        "is_captain": pick["is_captain"],
                        "is_vice_captain": pick["is_vice_captain"],
                        "position": pick["position"],
                        "load_timestamp": utc_now(),
                    })
                print(f"{entry_id} GW{gw}")
            except Exception as exc:
                print(f"{entry_id} GW{gw} failed: {exc}")

    df = pd.DataFrame(rows)
    if df.empty:
        return

    load_table_replace(df, TABLE_NAME, engine)
    print("Manager picks complete")
