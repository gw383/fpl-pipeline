"""Ingests per-gameweek live player stats ("event/<gw>/live") from the FPL API."""
from __future__ import annotations

import pandas as pd
import requests
from sqlalchemy.engine import Engine

from common import delete_gameweek_data, determine_gameweeks_to_fetch, load_table_append, utc_now
from config import CURRENT_SEASON

TABLE_NAME = "raw_event_live"


def fetch_event_live(gameweek: int) -> dict:
    """Fetch live per-player stats for a single gameweek."""
    url = f"https://fantasy.premierleague.com/api/event/{gameweek}/live/"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def event_live(engine: Engine, gameweeks: list[int]) -> None:
    """Incrementally ingest live stats for whichever of `gameweeks` still
    need it.

    This used to refetch and reload every gameweek in `gameweeks` (all
    38, every single run) regardless of whether that gameweek's data
    could possibly have changed since the last run. It now asks
    determine_gameweeks_to_fetch which ones actually still need a
    network call -- a gameweek that's already loaded *and* that FPL has
    finished double-checking (data_checked) is skipped entirely. Call
    this the same way as before, with the full season's gameweek list;
    it decides internally what actually needs fetching.
    """
    to_fetch = determine_gameweeks_to_fetch(engine, gameweeks, CURRENT_SEASON, TABLE_NAME)

    if not to_fetch:
        print("Event live: nothing to do, every gameweek is already up to date")
        return

    print(
        f"Starting event live ingestion "
        f"({len(to_fetch)} of {len(gameweeks)} gameweeks need updating)"
    )

    for gw in to_fetch:
        data = fetch_event_live(gw)
        elements = data.get("elements", [])

        if not elements:
            print(f"GW {gw}: not played yet, skipping")
            continue

        df = pd.json_normalize(elements)
        df["event_id"] = gw
        df["season"] = CURRENT_SEASON
        df["load_timestamp"] = utc_now()
        df.columns = [col.lower().replace(" ", "_") for col in df.columns]

        # Only this one gameweek's previous rows are cleared -- unlike
        # the old whole-season delete_season_data, gameweeks we didn't
        # just refetch are left untouched.
        delete_gameweek_data(engine, TABLE_NAME, CURRENT_SEASON, gw)
        load_table_append(df, TABLE_NAME, engine)

        print(f"Loaded GW {gw}")

    print("Event live ingestion complete")
