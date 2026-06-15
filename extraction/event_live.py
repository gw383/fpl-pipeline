import requests
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy import text

from config import CURRENT_SEASON

def fetch_event_live(gameweek):
    url = f"https://fantasy.premierleague.com/api/event/{gameweek}/live/"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def delete_season_data(engine, table_name, season):
    with engine.begin() as conn:
        conn.execute(
            text(f"""
                DELETE FROM raw.{table_name}
               WHERE season = :season
             """),
            {"season": season})

    print(f" Cleared {season} data from raw.{table_name}")


def load_table(df, table_name, engine):

    df["load_timestamp"] = df["load_timestamp"].astype(str)

    df.to_sql(
        table_name,
        engine,
        schema="raw",
        if_exists="append",
        index=False)

    print(f" Loaded raw.{table_name} ({len(df)} rows)")

def event_live(engine, gameweeks):

    print(f" Starting event live ingestion ({len(gameweeks)} gameweeks)")

    all_rows = []

    for gw in gameweeks:

        data = fetch_event_live(gw)

        elements = data.get("elements", [])

        if not elements:
            continue

        df = pd.json_normalize(elements)

        df["event_id"] = gw
        df["season"] = CURRENT_SEASON
        df["load_timestamp"] = datetime.now(timezone.utc)

        all_rows.append(df)

        print(f" Loaded GW {gw}")

    if not all_rows:
        print("⚠ No event live data returned")
        return

    final_df = pd.concat(all_rows, ignore_index=True)

    final_df.columns = [
        c.lower().replace(" ", "_")
        for c in final_df.columns]

    delete_season_data(engine, "raw_event_live", CURRENT_SEASON)

    load_table(final_df, "raw_event_live", engine)

    print("✅ Event live ingestion complete")