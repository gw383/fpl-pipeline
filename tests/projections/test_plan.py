"""Tests for projections/plan.py (squad planning)."""

import numpy as np
import pandas as pd
import pytest

from league import league
from model import ModelConfig, project

pytest.importorskip("scipy")  # the planner's optimiser (in requirements.txt)

from plan import FORMATION, MAX_PER_CLUB, SQUAD, evaluate, gameweek_points, optimise, weekly_summary  # noqa: E402

GWS = [6, 7, 8]


def market(seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """20 clubs x 6 players (1 GK, 2 DEF, 2 MID, 1 FWD); expected points
    rise with price, plus noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for team in range(1, 21):
        for position in (1, 2, 2, 3, 3, 4):
            price = round(float(rng.uniform(4.0, 12.0 if position > 1 else 6.0)), 1)
            rows.append((len(rows) + 1, team, position, price))
    players = pd.DataFrame(rows, columns=["p_id", "p_team", "p_position", "price"])
    base = 1.0 + 0.5 * players["price"] + rng.normal(0, 0.5, len(players))
    points = pd.DataFrame({gw: base + rng.normal(0, 0.3, len(players)) for gw in GWS})
    points.index = players["p_id"]
    return players, points


def check_valid(plan, players, budget):
    squad = plan.squad
    assert len(squad) == 15
    assert squad["p_position"].value_counts().to_dict() == SQUAD
    assert squad["p_team"].value_counts().max() <= MAX_PER_CLUB
    assert squad["price"].sum() <= budget + 1e-6
    position = players.set_index("p_id")["p_position"]
    for lineup in plan.lineups.values():
        assert len(lineup["starters"]) == 11 and lineup["captain"] in lineup["starters"]
        counts = position[lineup["starters"]].value_counts()
        for pos, (lo, hi) in FORMATION.items():
            assert lo <= counts.get(pos, 0) <= hi


def test_wildcard_squad_is_valid_and_uses_the_budget():
    players, points = market()
    rich = optimise(players, points, budget=100.0)
    check_valid(rich, players, 100.0)
    poor = optimise(players, points, budget=80.0)
    check_valid(poor, players, 80.0)
    assert poor.objective < rich.objective


def test_no_transfers_keeps_the_squad():
    players, points = market()
    current = list(optimise(players, points, budget=90.0).squad["p_id"])
    kept = optimise(players, points, budget=90.0, current=current, max_transfers=0)
    assert sorted(kept.squad["p_id"]) == sorted(current) and kept.hits == 0


def test_transfer_brings_in_a_standout_and_hits_only_when_worth_it():
    players, points = market()
    current = list(optimise(players, points, budget=90.0).squad["p_id"])
    # A cheap midfielder nobody owns suddenly projects 10 a week.
    star = players[(players["p_position"] == 3) & ~players["p_id"].isin(current)].nsmallest(1, "price")["p_id"].iloc[0]
    boosted = points.copy()
    boosted.loc[star] = 10.0
    plan = optimise(players, boosted, budget=90.0, current=current, free_transfers=1, max_transfers=1)
    assert plan.transfers_in == [star] and len(plan.transfers_out) == 1 and plan.hits == 0
    # With no free transfers, a small gain isn't worth a -4.
    small = points.copy()
    small.loc[star] = small.loc[plan.transfers_out[0]] + 0.2
    held = optimise(players, small, budget=90.0, current=current, free_transfers=0, max_transfers=1)
    assert held.transfers_in == [] and held.hits == 0


def test_later_gameweeks_count_for_less():
    projection = project(league(), 5, ModelConfig(horizon=3))
    raw, weighted = gameweek_points(projection, discount=0.5)
    first, last = raw.columns[0], raw.columns[-1]
    assert weighted[first].equals(raw[first])
    assert np.allclose(weighted[last], raw[last] * 0.25)


def test_locked_players_are_kept():
    players, points = market()
    worst_mid = players[players["p_position"] == 3].nsmallest(1, "price")["p_id"].iloc[0]
    plan = optimise(players, points, budget=100.0, locked={worst_mid})
    assert worst_mid in set(plan.squad["p_id"])
    check_valid(plan, players, 100.0)


def test_evaluate_and_weekly_summary():
    players, points = market()
    squad = list(optimise(players, points, budget=90.0).squad["p_id"])
    result = evaluate(players, points, squad)
    assert sorted(result.squad["p_id"]) == sorted(squad) and result.hits == 0
    weekly = weekly_summary(result, points, players.set_index("p_id")["p_position"])
    assert list(weekly["gw"]) == GWS
    for _, row in weekly.iterrows():
        lineup = result.lineups[row["gw"]]
        expected = points.loc[lineup["starters"], row["gw"]].sum() + points.loc[lineup["captain"], row["gw"]]
        assert row["points"] == pytest.approx(expected)
        assert sum(int(n) for n in row["formation"].split("-")) == 10


def test_fast_lineups_match_the_optimiser():
    players, points = market(seed=3)
    squad = list(optimise(players, points, budget=85.0).squad["p_id"])
    positions = players.set_index("p_id")["p_position"]
    fast = weekly_summary(evaluate(players, points, squad), points, positions)
    milp = weekly_summary(optimise(players, points, 1e9, current=squad, max_transfers=0), points, positions)
    assert list(fast["points"].round(6)) == list(milp["points"].round(6))
