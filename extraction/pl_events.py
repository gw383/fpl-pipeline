"""Ingest goal events from the Premier League's own match API.

FPL's data says who *missed* a penalty but not who *scored* one, and its xG
includes penalties. The Premier League website's API (the one behind
premierleague.com match centres) lists every goal with its type -- "Goal",
"Penalty" or "Own" -- so together they give every penalty taken, per player
per gameweek. The projection model uses that to separate penalty xG from
open-play xG.

Player and team IDs in this API are the same Opta codes FPL exposes as
``code`` on players and teams, so no name matching is needed.

One request lists a matchweek's matches, then one per finished match fetches
its events. Matchweeks are loaded incrementally like the live stats, and a
failure here is logged rather than stopping the rest of the pipeline (the
model simply skips the penalty split without this data).
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from common import RAW_SCHEMA, determine_gameweeks_to_fetch, fetch_url_json, replace_partition, table_exists, utc_now
from config import CURRENT_SEASON

logger = logging.getLogger(__name__)

PL_API_BASE_URL = "https://sdp-prem-prod.premier-league-prod.pulselive.com/api"
PL_COMPETITION_ID = 8  # Premier League
PL_HEADERS = {"Origin": "https://www.premierleague.com", "Referer": "https://www.premierleague.com/"}

TABLE_NAME = "raw_pl_goal_events"
TABLE_DDL = """
    match_id NVARCHAR(20), event_id BIGINT, home_team_code BIGINT, away_team_code BIGINT,
    scoring_side NVARCHAR(10), team_code BIGINT, player_code BIGINT, assist_code BIGINT,
    goal_type NVARCHAR(20), period NVARCHAR(20), minute NVARCHAR(10), season NVARCHAR(20),
    load_timestamp NVARCHAR(64)
"""

Row = dict[str, Any]


def pl_season_id(season_label: str) -> int:
    """The PL API's season ID is the starting year: "2026-27" -> 2026."""
    return int(season_label[:4])


def _int_or_none(value: Any) -> int | None:
    return int(value) if value not in (None, "") else None


def parse_match_goals(match: dict[str, Any], events: dict[str, Any], matchweek: int) -> list[Row]:
    """One row per goal in a match's events, from the scoring side's view.

    ``goal_type`` is "Goal", "Penalty" or "Own" (an own goal is listed under
    the side that benefited).
    """
    home, away = match["homeTeam"], match["awayTeam"]
    rows = []
    for side, team in (("home", home), ("away", away)):
        for goal in events.get(f"{side}Team", {}).get("goals") or []:
            rows.append(
                {
                    "match_id": str(match["matchId"]),
                    "event_id": matchweek,
                    "home_team_code": _int_or_none(home.get("id")),
                    "away_team_code": _int_or_none(away.get("id")),
                    "scoring_side": side,
                    "team_code": _int_or_none(team.get("id")),
                    "player_code": _int_or_none(goal.get("playerId")),
                    "assist_code": _int_or_none(goal.get("assistPlayerId")),
                    "goal_type": goal.get("goalType"),
                    "period": goal.get("period"),
                    "minute": goal.get("time"),
                }
            )
    return rows


def fetch_matchweek_goals(matchweek: int, season_id: int) -> list[Row]:
    """Every goal in a matchweek's finished matches."""
    matches = fetch_url_json(
        f"{PL_API_BASE_URL}/v1/competitions/{PL_COMPETITION_ID}/seasons/{season_id}/matchweeks/{matchweek}/matches?_limit=40",
        PL_HEADERS,
    ).get("data", [])
    rows: list[Row] = []
    for match in matches:
        if match.get("period") != "FullTime":
            continue
        events = fetch_url_json(f"{PL_API_BASE_URL}/v1/matches/{match['matchId']}/events", PL_HEADERS)
        rows.extend(parse_match_goals(match, events, matchweek))
    return rows


def ensure_goal_events_table(engine: Engine) -> None:
    """Create the (empty) raw table so dbt can build on it before the first load."""
    with engine.begin() as conn:
        if not table_exists(conn, TABLE_NAME):
            conn.execute(text(f"CREATE TABLE {RAW_SCHEMA}.{TABLE_NAME} ({TABLE_DDL})"))


def ingest_pl_goal_events(engine: Engine, gameweeks: list[int], refetch_all: bool = False) -> None:
    """Load goal events for whichever matchweeks still need it (matchweek
    numbers follow the FPL gameweeks; dbt maps each match to its FPL fixture
    by team, so rearranged matches still land in the right gameweek)."""
    ensure_goal_events_table(engine)
    to_fetch = (
        list(gameweeks) if refetch_all else determine_gameweeks_to_fetch(engine, gameweeks, CURRENT_SEASON, TABLE_NAME)
    )
    if not to_fetch:
        logger.info("PL goal events: every matchweek is already up to date")
        return

    season_id = pl_season_id(CURRENT_SEASON)
    logger.info("PL goal events: fetching %s matchweek(s)", len(to_fetch))
    for matchweek in to_fetch:
        rows = fetch_matchweek_goals(matchweek, season_id)
        if not rows:
            logger.info("PL goal events: no finished matches with goals in matchweek %s yet", matchweek)
            continue
        df = pd.DataFrame(rows).assign(season=CURRENT_SEASON, load_timestamp=utc_now())
        with engine.begin() as conn:
            replace_partition(conn, df, TABLE_NAME, CURRENT_SEASON, matchweek)


# ---------------------------------------------------------------------------
# Previous seasons (for the penalty split in players' season history)
# ---------------------------------------------------------------------------

PAST_SEASONS_WITH_PENALTIES = 2  # the history prior uses last season; two are kept so that can be revisited
MATCHWEEKS_PER_SEASON = 38


def previous_seasons(season_label: str, count: int) -> list[str]:
    """The ``count`` seasons before ``season_label``: "2026-27" -> ["2025-26", "2024-25"]."""
    start = pl_season_id(season_label)
    return [f"{year}-{str(year + 1)[-2:]}" for year in range(start - 1, start - 1 - count, -1)]


def _loaded_matchweeks(engine: Engine, season: str) -> set[int]:
    with engine.connect() as conn:
        query = text(f"SELECT DISTINCT event_id FROM {RAW_SCHEMA}.{TABLE_NAME} WHERE season = :season")
        return {int(row[0]) for row in conn.execute(query, {"season": season})}


def ingest_past_goal_events(engine: Engine, seasons: list[str] | None = None) -> None:
    """Load goal events for finished previous seasons, once: only matchweeks
    not already stored for that season are fetched, so after the first run
    this costs nothing."""
    ensure_goal_events_table(engine)
    for season in seasons or previous_seasons(CURRENT_SEASON, PAST_SEASONS_WITH_PENALTIES):
        missing = sorted(set(range(1, MATCHWEEKS_PER_SEASON + 1)) - _loaded_matchweeks(engine, season))
        if not missing:
            continue
        logger.info("PL goal events %s: fetching %s matchweek(s)", season, len(missing))
        season_id = pl_season_id(season)
        for matchweek in missing:
            rows = fetch_matchweek_goals(matchweek, season_id)
            if not rows:
                logger.warning("PL goal events %s: nothing for matchweek %s", season, matchweek)
                continue
            df = pd.DataFrame(rows).assign(season=season, load_timestamp=utc_now())
            with engine.begin() as conn:
                replace_partition(conn, df, TABLE_NAME, season, matchweek)
