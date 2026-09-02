import requests
import pandas as pd
from datetime import datetime, timezone


def fetch_transfers(entry_id):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/transfers/"
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

def manager_transfers(engine, entry_ids):

    print(f" Ingesting manager transfers")

    rows = []

    for eid in entry_ids:

        try:
            data = fetch_transfers(eid)

            for t in data:
                rows.append({
                    "entry_id": eid,
                    "element_in": t["element_in"],
                    "element_out": t["element_out"],
                    "event": t["event"],
                    "time": t["time"],
                    "load_timestamp": datetime.now(timezone.utc)
                })

            print(f"✔ Transfers {eid}")

        except Exception as e:
            print(f"⚠ Failed {eid}: {e}")

    df = pd.DataFrame(rows)

    if df.empty:
        return

    load_table(df, "raw_manager_transfers", engine)

    print(" Manager transfers complete")