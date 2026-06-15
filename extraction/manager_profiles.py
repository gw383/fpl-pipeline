import requests
import pandas as pd
from datetime import datetime, timezone


def fetch_entry(entry_id):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def load_table(df, table_name, engine):

    df["load_timestamp"] = df["load_timestamp"].astype(str)

    df.to_sql(
        table_name,
        engine,
        schema="raw",
        if_exists="replace",
        index=False)


def manager_profiles(engine, entry_ids):

    print(f" Ingesting manager profiles ({len(entry_ids)} managers)")

    rows = []

    for eid in entry_ids:

        try:
            data = fetch_entry(eid)

            rows.append({
                "entry_id": eid,
                "player_name": data.get("player_name"),
                "team_name": data.get("name"),
                "overall_points": data.get("summary_overall_points"),
                "overall_rank": data.get("summary_overall_rank"),
                "value": data.get("last_deadline_value"),
                "load_timestamp": datetime.now(timezone.utc)
            })

            print(f"✔ Loaded manager {eid}")

        except Exception as e:
            print(f"⚠ Failed {eid}: {e}")

    df = pd.DataFrame(rows)

    if df.empty:
        return

    load_table(df, "raw_manager_profiles", engine)

    print(" Manager profiles complete")