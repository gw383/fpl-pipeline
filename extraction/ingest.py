"""Extraction entry point: pull everything from the FPL API into ``raw``.

Run locally with ``python extraction/ingest.py`` or as the first task of the
Airflow DAG. Pass ``--refetch-all`` to reload every started gameweek's live
stats instead of only the ones that may have changed, and
``--refetch-history`` to reload every player's previous-season history
(normally fetched once per player per season).
"""

from __future__ import annotations

import argparse
import logging

from bootstrap_static import ingest_bootstrap_static, started_gameweeks
from common import ensure_raw_schema
from config import CURRENT_SEASON, TRACKED_ENTRY_IDS
from db import get_engine
from event_live import ingest_event_live
from fixtures import ingest_fixtures
from managers import ensure_manager_tables, ingest_managers, known_manager_ids
from pl_events import ensure_goal_events_table, ingest_past_goal_events, ingest_pl_goal_events
from player_history import ensure_history_tables, ingest_player_history

logger = logging.getLogger("ingest")


def run_pipeline(refetch_all: bool = False, refetch_history: bool = False) -> None:
    """Run every extraction step, in dependency order, on one engine."""
    engine = get_engine()
    ensure_raw_schema(engine)

    logger.info("Ingesting season %s", CURRENT_SEASON)

    bootstrap = ingest_bootstrap_static(engine)
    gameweeks = started_gameweeks(bootstrap["events"])
    logger.info("%s gameweeks have started", len(gameweeks))

    ingest_fixtures(engine)
    ingest_event_live(engine, gameweeks, refetch_all=refetch_all)

    # Penalty data from the Premier League's match API. Optional: if it's
    # unavailable the projection model just skips the penalty split.
    try:
        ingest_pl_goal_events(engine, gameweeks, refetch_all=refetch_all)
    except Exception as exc:  # a third-party API shouldn't block the FPL load
        logger.warning("PL goal events: skipped (%s)", exc)
        ensure_goal_events_table(engine)

    # Players' previous Premier League seasons (a prior for the projection
    # model). Once a season: only players not loaded yet are fetched. The
    # previous seasons' goal events give those seasons' penalties.
    try:
        ingest_player_history(engine, bootstrap["elements"], refetch=refetch_history)
    except Exception as exc:  # the model falls back to price-only priors
        logger.warning("Player history: skipped (%s)", exc)
        ensure_history_tables(engine)
    try:
        ingest_past_goal_events(engine)
    except Exception as exc:
        logger.warning("PL goal events (previous seasons): skipped (%s)", exc)

    # Configured managers plus any looked up in the dashboard since.
    ensure_manager_tables(engine)
    entry_ids = sorted(set(TRACKED_ENTRY_IDS) | set(known_manager_ids(engine)))
    if entry_ids:
        logger.info("Refreshing %s manager(s)", len(entry_ids))
        ingest_managers(engine, entry_ids, gameweeks)
    else:
        logger.info("No managers configured or looked up yet; skipping manager data")

    logger.info("Extraction complete")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--refetch-all",
        action="store_true",
        help="reload live stats for every started gameweek, not just new/unsettled ones",
    )
    parser.add_argument(
        "--refetch-history",
        action="store_true",
        help="reload every player's previous-season history (normally loaded once a season)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_pipeline(refetch_all=args.refetch_all, refetch_history=args.refetch_history)


if __name__ == "__main__":
    main()
