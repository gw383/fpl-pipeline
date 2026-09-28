"""Entry point for the extraction stage of the pipeline.

Run directly (`python ingest.py`) or as the first task in the Airflow
DAG. Pulls bootstrap reference data, fixtures, live gameweek stats and
manager data for TRACKED_ENTRY_IDS, in that order.
"""
from __future__ import annotations

from db import get_engine
from event_live import event_live
from fixtures import fixtures
from main_endpoint import main_endpoint
from manager_picks import manager_picks
from manager_profiles import manager_profiles
from manager_transfers import manager_transfers

# FPL manager entry IDs to track. Add more IDs here to follow
# additional managers/mini-leagues.
# 194625 is the user's own FPL manager ID, added to back the "My Team"
# page (StreamLit/pages/MyTeam.py) -- see CHANGELOG.md.
TRACKED_ENTRY_IDS = [146897, 194625]

# A Premier League season runs 38 gameweeks.
ALL_GAMEWEEKS = list(range(1, 39))


def run_pipeline() -> None:
    """Run every extraction step in sequence against one shared engine."""
    engine = get_engine()

    print("\nSTARTING FPL PIPELINE\n")

    main_endpoint(engine)
    fixtures(engine)
    event_live(engine, ALL_GAMEWEEKS)

    print("\nIngesting manager profiles...")
    manager_profiles(engine, TRACKED_ENTRY_IDS)

    print("\nIngesting manager picks...")
    manager_picks(engine, TRACKED_ENTRY_IDS, ALL_GAMEWEEKS)

    print("\nIngesting manager transfers...")
    manager_transfers(engine, TRACKED_ENTRY_IDS)

    print("\nPIPELINE COMPLETE")


if __name__ == "__main__":
    run_pipeline()
