"""Ingests each manager's transfer history."""
from __future__ import annotations

import pandas as pd
import requests
from sqlalchemy.engine import Engine

from common import load_table_replace, utc_now

TABLE_NAME = "raw_manager_transfers"


def fetch_transfers(entry_id: int) -> list[dict]:
    """Fetch a manager's full transfer history."""
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/transfers/"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def manager_transfers(engine: Engine, entry_ids: list[int]) -> None:
    """Ingest transfer history for every manager in `entry_ids`."""
    print("Ingesting manager transfers")

    rows = []
    for entry_id in entry_ids:
        try:
            for transfer in fetch_transfers(entry_id):
                rows.append({
                    "entry_id": entry_id,
                    "element_in": transfer["element_in"],
                    "element_out": transfer["element_out"],
                    "event": transfer["event"],
                    "time": transfer["time"],
                    "load_timestamp": utc_now(),
                })
            print(f"Transfers {entry_id}")
        except Exception as exc:
            print(f"Failed {entry_id}: {exc}")

    df = pd.DataFrame(rows)
    if df.empty:
        return

    load_table_replace(df, TABLE_NAME, engine)
    print("Manager transfers complete")
