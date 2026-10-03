"""SQL-building helpers shared by the query modules (pure, no database).

The dashboard's queries run against its data file, which is SQLite (see
``database.py``), so this is SQLite's dialect: ``datetime('now')`` for the
current UTC time and ``limit`` for the first rows. Timestamps in the file
are UTC text in the same ``YYYY-MM-DD HH:MM:SS`` shape, so they compare
with it directly."""

from __future__ import annotations

import re

# Range selector label -> number of most recent played gameweeks (None = all).
RANGE_OPTIONS: dict[str, int | None] = {
    "All gameweeks": None,
    "Last 10 gameweeks": 10,
    "Last 5 gameweeks": 5,
}

NOW_SQL = "datetime('now')"

# Gameweeks whose deadline has passed / is still to come.
PLAYED_GAMEWEEKS_SQL = f"gw_deadline_time < {NOW_SQL}"
UPCOMING_GAMEWEEKS_SQL = f"gw_deadline_time >= {NOW_SQL}"

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def range_filter_sql(range_label: str, gw_column: str = "gw_id") -> str:
    """A boolean SQL predicate restricting ``gw_column`` to the selected range.

    Only values from :data:`RANGE_OPTIONS` are accepted, and the column must
    be a plain (optionally table-qualified) identifier, so the fragment is
    safe to embed in a query.
    """
    if range_label not in RANGE_OPTIONS:
        raise ValueError(f"Unknown range {range_label!r}; expected one of {list(RANGE_OPTIONS)}")
    if not _IDENTIFIER.match(gw_column):
        raise ValueError(f"Invalid column name {gw_column!r}")

    last_n = RANGE_OPTIONS[range_label]
    if last_n is None:
        return "(1 = 1)"
    return f"""({gw_column} in (
        select gw_id
        from analytics.gameweeks
        where {PLAYED_GAMEWEEKS_SQL}
        order by gw_id desc
        limit {last_n}
    ))"""
