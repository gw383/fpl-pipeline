import requests
import pandas as pd
from datetime import datetime, timezone


# ----------------------------
# FETCH
# ----------------------------

def fetch_picks(entry_id, gw):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


# ----------------------------
# LOAD
# ----------------------------

def load_table(df, table_name, engine):

    df["load_timestamp"] = df["load_timestamp"].astype(str)

    df.to_sql(
        table_name,
        engine,
        schema="raw",
        if_exists="replace",
        index=False
    )


# ----------------------------
# MAIN
# ----------------------------

def ingest_manager_picks(engine, entry_ids, gameweeks):

    print(f"🚀 Ingesting manager picks")

    rows = []

    for eid in entry_ids:
        for gw in gameweeks:

            try:
                data = fetch_picks(eid, gw)

                for p in data.get("picks", []):
                    rows.append({
                        "entry_id": eid,
                        "event_id": gw,
                        "player_id": p["element"],
                        "multiplier": p["multiplier"],
                        "is_captain": p["is_captain"],
                        "is_vice_captain": p["is_vice_captain"],
                        "position": p["position"],
                        "load_timestamp": datetime.now(timezone.utc)
                    })

                print(f"✔ {eid} GW{gw}")

            except Exception as e:
                print(f"⚠ {eid} GW{gw} failed: {e}")

    df = pd.DataFrame(rows)

    if df.empty:
        return

    load_table(df, "raw_manager_picks", engine)

    print("✅ Manager picks complete")