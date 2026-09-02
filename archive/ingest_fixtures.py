import requests
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy import text

from config import CURRENT_SEASON


# ----------------------------
# HELPERS
# ----------------------------

def fetch_fixtures():
    """
    Retrieves fixture data from FPL API.
    """
    url = "https://fantasy.premierleague.com/api/fixtures/"

    response = requests.get(url)
    response.raise_for_status()

    return response.json()


def delete_season_data(engine, table_name, season):

    with engine.begin() as conn:
        result = conn.execute(
            text(f"""
                DELETE FROM raw.{table_name}
                WHERE season = :season
            """),
            {"season": season}
        )

        print(f"Deleted {result.rowcount} rows from raw.{table_name}")

    print(f"🧹 Cleared {season} data from raw.{table_name}")


def load_table(df, table_name, engine):
    """
    Loads dataframe into SQL Server.
    Assumes season-level delete already done.
    """

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
# MAIN INGESTION FUNCTION
# ----------------------------

def ingest_fixtures(engine):

    print("🚀 Starting fixtures ingestion...")

    # ----------------------------
    # FETCH DATA
    # ----------------------------

    fixtures = pd.DataFrame(fetch_fixtures())

    if fixtures.empty:
        print("⚠ No fixture data returned")
        return

    # ----------------------------
    # CLEAN COLUMN NAMES
    # ----------------------------

    fixtures.columns = [
        col.lower().replace(" ", "_")
        for col in fixtures.columns
    ]

    # ----------------------------
    # ADD METADATA
    # ----------------------------

    load_time = datetime.now(timezone.utc)

    fixtures["load_timestamp"] = load_time
    fixtures["season"] = CURRENT_SEASON

    # ----------------------------
    # DELETE EXISTING SEASON DATA
    # ----------------------------

    delete_season_data(engine, "raw_fixtures", CURRENT_SEASON)

    # ----------------------------
    # LOAD INTO SQL SERVER
    # ----------------------------

    load_table(
        fixtures,
        "raw_fixtures",
        engine
    )

    print("✅ Fixtures ingestion complete")