"""Ingests each manager's gameweek-by-gameweek picks, plus (from the
same response, no extra network call) that gameweek's points/rank/
value/transfers snapshot and any chip played.
"""
from __future__ import annotations

import pandas as pd
import requests
from sqlalchemy.engine import Engine

from common import load_table_replace, utc_now

TABLE_NAME = "raw_manager_picks"
HISTORY_TABLE_NAME = "raw_manager_gameweek_history"


def fetch_picks(entry_id: int, gameweek: int) -> dict:
    """Fetch one manager's picks for a single gameweek."""
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gameweek}/picks/"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def manager_picks(engine: Engine, entry_ids: list[int], gameweeks: list[int]) -> None:
    """Ingest picks -- and the per-gameweek history snapshot alongside
    them -- for every (manager, gameweek) combination.

    The FPL API's picks response already carries two other things
    besides the picks list itself, in the same payload: "entry_history"
    (that gameweek's points, overall rank, bank, squad value, transfers
    made and any transfer-cost points hit, and points left on the
    bench) and "active_chip" (which chip, if any, was played that
    gameweek). Neither was being captured before -- only the picks list
    was. Reading both out of the response we're already fetching, into
    a second table (HISTORY_TABLE_NAME), avoids a second round of API
    calls just to get information this endpoint was handing over anyway.
    Built for the My Team page (StreamLit/pages/MyTeam.py) -- see
    CHANGELOG.md.
    """
    print("Ingesting manager picks")

    pick_rows = []
    history_rows = []
    for entry_id in entry_ids:
        for gw in gameweeks:
            try:
                data = fetch_picks(entry_id, gw)
                for pick in data.get("picks", []):
                    pick_rows.append({
                        "entry_id": entry_id,
                        "event_id": gw,
                        "player_id": pick["element"],
                        "multiplier": pick["multiplier"],
                        "is_captain": pick["is_captain"],
                        "is_vice_captain": pick["is_vice_captain"],
                        "position": pick["position"],
                        "load_timestamp": utc_now(),
                    })

                history = data.get("entry_history") or {}
                if history:
                    history_rows.append({
                        "entry_id": entry_id,
                        "event_id": gw,
                        "points": history.get("points"),
                        "total_points": history.get("total_points"),
                        "overall_rank": history.get("overall_rank"),
                        "bank": history.get("bank"),
                        "value": history.get("value"),
                        "event_transfers": history.get("event_transfers"),
                        "event_transfers_cost": history.get("event_transfers_cost"),
                        "points_on_bench": history.get("points_on_bench"),
                        "active_chip": data.get("active_chip"),
                        "load_timestamp": utc_now(),
                    })

                print(f"{entry_id} GW{gw}")
            except Exception as exc:
                print(f"{entry_id} GW{gw} failed: {exc}")

    picks_df = pd.DataFrame(pick_rows)
    if not picks_df.empty:
        load_table_replace(picks_df, TABLE_NAME, engine)

    history_df = pd.DataFrame(history_rows)
    if not history_df.empty:
        load_table_replace(history_df, HISTORY_TABLE_NAME, engine)

    print("Manager picks complete")
