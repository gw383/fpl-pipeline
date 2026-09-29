"""Runtime configuration for the extraction pipeline.

Every setting can be overridden with an environment variable (or a ``.env``
file in the project root -- see ``.env.example``), so the same code runs
unchanged on a laptop and inside the Airflow containers.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def parse_id_list(value: str) -> list[int]:
    """Parse a comma-separated list of integer IDs, e.g. ``"123, 456"``."""
    try:
        return [int(part) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise ValueError(f"Expected a comma-separated list of integers, got {value!r}") from exc


# Season label stamped onto every raw row. Must match a ``display_name`` in
# transformation/seeds/seasons.csv -- the dbt staging models use it to pick
# out the current season's data.
CURRENT_SEASON: str = os.getenv("FPL_SEASON", "2026-27")

# FPL manager ("entry") IDs whose profile, picks and transfers are always
# ingested. Any public FPL team can be tracked; managers looked up on the
# dashboard's My Team page are added to the warehouse and refreshed on every
# run as well (see managers.known_manager_ids).
TRACKED_ENTRY_IDS: list[int] = parse_id_list(os.getenv("FPL_ENTRY_IDS", "146897,194625"))

FPL_API_BASE_URL = "https://fantasy.premierleague.com/api"
REQUEST_TIMEOUT_SECONDS = 30
