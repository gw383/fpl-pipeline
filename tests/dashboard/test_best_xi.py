"""Tests for dashboard/best_xi.py."""

import pandas as pd

from best_xi import pick_best_xi


def _players(counts: dict[int, list[float]]) -> pd.DataFrame:
    rows = [
        {"p_id": pos * 100 + i, "player": f"P{pos}-{i}", "p_position": pos, "points": value}
        for pos, values in counts.items()
        for i, value in enumerate(values)
    ]
    return pd.DataFrame(rows)


def test_picks_formation_with_highest_total():
    # Strong forwards and weak defenders -> a 3-4-3 beats every other shape.
    players = _players({1: [5, 1], 2: [1, 1, 1, 1, 1], 3: [3, 3, 3, 3, 3], 4: [9, 9, 9]})
    formation, xi = pick_best_xi(players, "points")
    assert formation == "3-4-3"
    assert len(xi) == 11
    assert xi["p_position"].value_counts().to_dict() == {1: 1, 2: 3, 3: 4, 4: 3}


def test_back_five_when_defenders_dominate():
    players = _players({1: [5], 2: [9, 9, 9, 9, 9], 3: [1, 1, 1, 1, 1], 4: [1, 1, 1]})
    formation, _ = pick_best_xi(players, "points")
    assert formation.startswith("5-")


def test_best_players_chosen_and_ordered_within_position():
    players = _players({1: [1, 7], 2: [4, 8, 6, 2, 5], 3: [3, 3, 3, 3, 3], 4: [2, 2, 2]})
    _, xi = pick_best_xi(players, "points")
    assert xi[xi["p_position"] == 1]["metric_value"].tolist() == [7]
    defenders = xi[xi["p_position"] == 2]["metric_value"].tolist()
    assert defenders == sorted(defenders, reverse=True)
    assert defenders[0] == 8


def test_missing_values_count_as_zero():
    players = _players({1: [None], 2: [1, 1, 1], 3: [1, 1, 1, 1], 4: [1, 1, 1]})
    _, xi = pick_best_xi(players, "points")
    assert xi["metric_value"].notna().all()


def test_empty_input():
    formation, xi = pick_best_xi(pd.DataFrame(columns=["p_position", "points"]), "points")
    assert formation is None and xi.empty
