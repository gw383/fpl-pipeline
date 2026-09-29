"""SQL-building helpers shared by the query modules (pure, no database)."""

from __future__ import annotations

import re

# Range selector label -> number of most recent played gameweeks (None = all).
RANGE_OPTIONS: dict[str, int | None] = {
    "All gameweeks": None,
    "Last 10 gameweeks": 10,
    "Last 5 gameweeks": 5,
}

# Gameweeks whose deadline has passed.
PLAYED_GAMEWEEKS_SQL = "gw_deadline_time < getdate()"

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
        select top ({last_n}) gw_id
        from analytics.gameweeks
        where {PLAYED_GAMEWEEKS_SQL}
        order by gw_id desc
    ))"""
