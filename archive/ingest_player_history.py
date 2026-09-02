import requests
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy import text

from config import CURRENT_SEASON


# ----------------------------
# HELPERS
# ----------------------------

def fetch_json(url):
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
            {"season": season}
        )

    print(f"🧹 Cleared {season} data from raw.{table_name}")


def load_table(df, table_name, engine):

    df["load_timestamp"] = df["load_timestamp"].astype(str)

    df.to_sql(
        table_name,
        engine,
        schema="raw",
        if_exists="append",
        index=False
    )

    print(f"✔ Loaded raw.{table_name} ({len(df)} rows)")


# ----------------------------
# MAIN INGESTION
# ----------------------------

def ingest_player_history(engine, gameweeks):

    print(f"🚀 Starting player history ingestion via event_live ({len(gameweeks)} GW)")

    # clear current season only
    delete_season_data(engine, "raw_player_history", CURRENT_SEASON)

    all_rows = []

    for gw in gameweeks:

        try:
            url = f"https://fantasy.premierleague.com/api/event/{gw}/live/"
            data = fetch_json(url)

            elements = data.get("elements", [])
            df = pd.DataFrame(elements)

            if df.empty:
                continue

            # ----------------------------
            # metadata
            # ----------------------------
            df["gameweek_id"] = gw
            df["load_timestamp"] = datetime.now(timezone.utc)
            df["season"] = CURRENT_SEASON

            all_rows.append(df)

            print(f"✔ Loaded GW {gw}")

        except Exception as e:
            print(f"⚠ Failed GW {gw}: {e}")

    if not all_rows:
        print("⚠ No data returned")
        return

    final_df = pd.concat(all_rows, ignore_index=True)

    # ----------------------------
    # clean column names
    # ----------------------------
    final_df.columns = [
        c.lower().replace(" ", "_") for c in final_df.columns
    ]

    load_table(final_df, "raw_player_history", engine)

    print("✅ Player history ingestion complete")
