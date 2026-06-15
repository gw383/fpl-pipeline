import requests
import pandas as pd
from datetime import datetime, timezone
import json
from sqlalchemy import text

from config import CURRENT_SEASON

def fetch_bootstrap_data():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def convert_nested_to_json(df):
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
            df[col] = df[col].apply(
                lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
    return df

def delete_season_data(engine, table_name, season):
    with engine.begin() as conn:
        conn.execute(
            text(f"""DELETE FROM raw.{table_name} WHERE season = :season"""),
            {"season": season})

    print(f"Cleared {season} data from raw.{table_name}")


def load_table(df, table_name, engine):
    df["load_timestamp"] = df["load_timestamp"].astype(str)

    df.to_sql(
        table_name,
        engine,
        schema="raw",
        if_exists="append",
        index=False)

    print(f"Loaded raw.{table_name} ({len(df)} rows)")



def main_endpoint(engine):

    print("Starting bootstrap-static ingestion...")

    data = fetch_bootstrap_data()

    players = pd.DataFrame(data["elements"])
    teams = pd.DataFrame(data["teams"])
    positions = pd.DataFrame(data["element_types"])
    gameweeks = pd.DataFrame(data["events"])

    load_time = datetime.now(timezone.utc)

    for df in [players, teams, positions, gameweeks]:
        df["load_timestamp"] = load_time
        df["season"] = CURRENT_SEASON

    players = convert_nested_to_json(players)
    teams = convert_nested_to_json(teams)
    positions = convert_nested_to_json(positions)
    gameweeks = convert_nested_to_json(gameweeks)

    delete_season_data(engine, "raw_players", CURRENT_SEASON)
    delete_season_data(engine, "raw_teams", CURRENT_SEASON)
    delete_season_data(engine, "raw_positions", CURRENT_SEASON)
    delete_season_data(engine, "raw_gameweeks", CURRENT_SEASON)

    load_table(players, "raw_players", engine)
    load_table(teams, "raw_teams", engine)
    load_table(positions, "raw_positions", engine)
    load_table(gameweeks, "raw_gameweeks", engine)

    print("✅ Bootstrap-static ingestion complete")