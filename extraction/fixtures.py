import requests
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy import text

from config import CURRENT_SEASON

def fetch_fixtures():
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
            {"season": season})

        print(f"Deleted {result.rowcount} rows from raw.{table_name}")

    print(f" Cleared {season} data from raw.{table_name}")


def load_table(df, table_name, engine):
    df["load_timestamp"] = df["load_timestamp"].astype(str)

    df.to_sql(
        table_name,
        engine,
        schema="raw",
        if_exists="append",
        index=False)

    print(f"✔ Loaded raw.{table_name} ({len(df)} rows)")

def fixtures(engine):

    print(" Starting fixtures ingestion...")

    fixtures = pd.DataFrame(fetch_fixtures())

    if fixtures.empty:
        print("⚠ No fixture data returned")
        return

    fixtures.columns = [
        col.lower().replace(" ", "_")
        for col in fixtures.columns]

    load_time = datetime.now(timezone.utc)

    fixtures["load_timestamp"] = load_time
    fixtures["season"] = CURRENT_SEASON

    delete_season_data(engine, "raw_fixtures", CURRENT_SEASON)


    load_table(
        fixtures,
        "raw_fixtures",
        engine)

    print("✅ Fixtures ingestion complete")