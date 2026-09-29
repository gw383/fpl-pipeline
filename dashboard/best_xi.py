"""Pick the highest-scoring valid FPL starting XI for a given metric."""

from __future__ import annotations

import pandas as pd

# (name, defenders, midfielders, forwards) -- every legal FPL formation.
FORMATIONS = [
    ("3-4-3", 3, 4, 3),
    ("3-5-2", 3, 5, 2),
    ("4-3-3", 4, 3, 3),
    ("4-4-2", 4, 4, 2),
    ("4-5-1", 4, 5, 1),
    ("5-3-2", 5, 3, 2),
    ("5-4-1", 5, 4, 1),
]


def pick_best_xi(players: pd.DataFrame, metric: str) -> tuple[str | None, pd.DataFrame]:
    """Choose the formation whose best 1 GK + N DEF/MID/FWD maximise ``metric``.

    ``players`` needs ``p_position`` (1-4) and the ``metric`` column. Returns
    the formation name and the selected rows (with a ``metric_value`` column),
    ordered goalkeeper -> forwards and best first within each position. The
    first formation in :data:`FORMATIONS` wins a tie.
    """
    if players.empty:
        return None, players.assign(metric_value=pd.Series(dtype=float))

    ranked = players.assign(metric_value=players[metric].fillna(0)).sort_values(
        ["p_position", "metric_value"], ascending=[True, False], kind="stable"
    )
    by_position = {pos: group for pos, group in ranked.groupby("p_position", sort=True)}

    def top(position: int, n: int) -> pd.DataFrame:
        return by_position.get(position, ranked.iloc[0:0]).head(n)

    best_name, best_score, best_xi = None, float("-inf"), ranked.iloc[0:0]
    for name, defenders, midfielders, forwards in FORMATIONS:
        xi = pd.concat([top(1, 1), top(2, defenders), top(3, midfielders), top(4, forwards)])
        score = xi["metric_value"].sum()
        if score > best_score:
            best_name, best_score, best_xi = name, score, xi

    return best_name, best_xi
