"""Shared ingestion helpers used across the extraction scripts.

Every raw-loading script follows one of two patterns:

* Season-partitioned tables (players, teams, fixtures, gameweeks,
  event-live stats) delete the current season's rows and append the
  freshly-fetched replacement, so re-running mid-season never creates
  duplicates.
* Manager-specific snapshots (profiles, picks, transfers) simply
  replace the whole table, since they only ever need to hold the
  latest pull for a small, hand-maintained list of FPL entry IDs.

Centralising both patterns here means every ingestion script shares
one implementation instead of five near-identical copies.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

RAW_SCHEMA = "raw"


def utc_now() -> datetime:
    """Return the current UTC timestamp used to stamp every load."""
    return datetime.now(timezone.utc)


def convert_nested_to_json(df: pd.DataFrame) -> pd.DataFrame:
    """Serialise any dict/list columns in `df` to JSON strings.

    SQL Server has no native column type for nested structures, so any
    column holding dicts or lists (as the FPL API sometimes returns)
    is flattened to JSON text before loading.
    """
    for col in df.columns:
        if df[col].apply(lambda value: isinstance(value, (dict, list))).any():
            df[col] = df[col].apply(
                lambda value: json.dumps(value)
                if isinstance(value, (dict, list))
                else value
            )
    return df


def delete_season_data(engine: Engine, table_name: str, season: str) -> None:
    """Delete existing rows for `season` from raw.`table_name`.

    Called before an append-style load so re-running the pipeline for
    the same season never creates duplicate rows.
    """
    with engine.begin() as conn:
        result = conn.execute(
            text(f"DELETE FROM {RAW_SCHEMA}.{table_name} WHERE season = :season"),
            {"season": season},
        )
        print(
            f"Cleared {season} data from {RAW_SCHEMA}.{table_name} "
            f"({result.rowcount} rows)"
        )


def delete_gameweek_data(
    engine: Engine, table_name: str, season: str, gameweek: int
) -> None:
    """Delete existing rows for one `season` + `gameweek` from
    raw.`table_name`.

    Used by incremental loaders (see determine_gameweeks_to_fetch) that
    only want to refresh specific gameweeks -- the ones that are new or
    not yet finalised -- rather than the whole season.
    """
    with engine.begin() as conn:
        result = conn.execute(
            text(
                f"DELETE FROM {RAW_SCHEMA}.{table_name} "
                f"WHERE season = :season AND event_id = :gameweek"
            ),
            {"season": season, "gameweek": gameweek},
        )
        print(
            f"Cleared season {season} GW{gameweek} data from "
            f"{RAW_SCHEMA}.{table_name} ({result.rowcount} rows)"
        )


def get_ingested_values(
    engine: Engine, table_name: str, season: str, column: str
) -> set:
    """Return the distinct `column` values already loaded into
    raw.`table_name` for `season`.

    E.g. get_ingested_values(engine, "raw_event_live", "2026-27", "event_id")
    returns the set of gameweek numbers already ingested this season.
    """
    with engine.begin() as conn:
        result = conn.execute(
            text(
                f"SELECT DISTINCT {column} FROM {RAW_SCHEMA}.{table_name} "
                f"WHERE season = :season"
            ),
            {"season": season},
        )
        return {row[0] for row in result}


# How many of the most-recently-ingested gameweeks stay in the refetch
# pool even after FPL marks them data_checked -- see the "Newcastle vs
# Leeds showing 0 for every stat" incident in CHANGELOG.md for exactly
# why this exists. That gameweek's live stats for one specific match
# were almost certainly captured mid-lag (this pipeline's one and only
# ingestion run for that gameweek happened to land in the narrow window
# where the rest of the gameweek had already posted but this one match's
# provider data hadn't yet), and once FPL flipped data_checked to true
# shortly after, _gameweeks_needing_fetch had no way of knowing its own
# earlier capture was incomplete -- "ingested + checked" was already
# true, so it silently stopped looking at that gameweek forever. FPL's
# own data_checked flag exists precisely because a gameweek's stats can
# still be corrected for a day or two after it finishes; this constant
# gives our own pipeline the same kind of grace period, on our side,
# against exactly that kind of one-match lag landing in a single
# snapshot right before "checked" flips. 2 gameweeks is roughly a
# fortnight of real time (gameweeks are ~weekly) -- comfortably past
# FPL's own correction window -- without permanently re-fetching a
# whole season's worth of already-settled gameweeks on every run.
GRACE_GAMEWEEKS = 2


def _gameweeks_needing_fetch(
    all_gameweeks: list[int], ingested: set, checked: dict
) -> list[int]:
    """Pure decision logic behind determine_gameweeks_to_fetch, split out
    so it can be unit tested without a database connection (see
    tests/test_common.py).

    A gameweek needs fetching if any of these hold:
      * it isn't in `ingested` yet, or
      * it has been ingested, but `checked` doesn't mark it as
        data_checked (i.e. FPL hadn't finished double-checking its
        stats and bonus points as of the last bootstrap-static load) --
        these can still be corrected for a day or two after a
        gameweek's fixtures finish, or
      * it's one of the GRACE_GAMEWEEKS most recently ingested
        gameweeks (by gameweek number), even if already checked -- a
        safety margin against a bad capture on our own side slipping
        through right as data_checked flips (see GRACE_GAMEWEEKS above).

    A gameweek with no entry in `checked` at all is treated as not yet
    checked, so it's still fetched -- this only ever means an extra
    safe fetch, never a skipped one.
    """
    already_ingested = sorted(gw for gw in all_gameweeks if gw in ingested)
    grace_window = set(already_ingested[-GRACE_GAMEWEEKS:])

    return [
        gw
        for gw in all_gameweeks
        if gw not in ingested or not checked.get(gw, False) or gw in grace_window
    ]


def determine_gameweeks_to_fetch(
    engine: Engine,
    all_gameweeks: list[int],
    season: str,
    event_live_table: str = "raw_event_live",
) -> list[int]:
    """Work out which of `all_gameweeks` still need (re-)fetching.

    A gameweek that's both already ingested into raw.`event_live_table`
    and marked data_checked in raw.raw_gameweeks is treated as settled
    and skipped -- this is what turns event_live's load from a full
    re-fetch of every gameweek on every run into an incremental one.
    "Settled" isn't quite "never touched again" any more, though: the
    GRACE_GAMEWEEKS most recently ingested gameweeks keep getting
    refetched for a while even once checked, as a safety margin against
    a bad one-off capture slipping through right as data_checked flips
    (see GRACE_GAMEWEEKS's own comment for the incident that motivated
    this). Only once a gameweek has aged out of that trailing window is
    it truly final (short of a manual re-ingest). See
    _gameweeks_needing_fetch for the actual decision logic.
    """
    ingested = get_ingested_values(engine, event_live_table, season, "event_id")

    with engine.begin() as conn:
        result = conn.execute(
            text(
                f"SELECT id, data_checked FROM {RAW_SCHEMA}.raw_gameweeks "
                f"WHERE season = :season"
            ),
            {"season": season},
        )
        checked = {row[0]: bool(row[1]) for row in result}

    return _gameweeks_needing_fetch(all_gameweeks, ingested, checked)


def load_table_append(df: pd.DataFrame, table_name: str, engine: Engine) -> None:
    """Append `df` to raw.`table_name`.

    Used for season-partitioned tables, after `delete_season_data` has
    already removed that season's previous rows.
    """
    df["load_timestamp"] = df["load_timestamp"].astype(str)
    df.to_sql(table_name, engine, schema=RAW_SCHEMA, if_exists="append", index=False)
    print(f"Loaded {RAW_SCHEMA}.{table_name} ({len(df)} rows)")


def load_table_replace(df: pd.DataFrame, table_name: str, engine: Engine) -> None:
    """Replace raw.`table_name` entirely with `df`.

    Used for manager-specific snapshots, which only ever need to hold
    the latest pull rather than a running history.
    """
    df["load_timestamp"] = df["load_timestamp"].astype(str)
    df.to_sql(table_name, engine, schema=RAW_SCHEMA, if_exists="replace", index=False)
    print(f"Loaded {RAW_SCHEMA}.{table_name} ({len(df)} rows)")
