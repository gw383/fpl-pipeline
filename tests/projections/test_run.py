"""Tests for projections/run.py."""

from dataclasses import replace

from league import league
from run import gameweek_expectations, started_gameweeks


def test_expectations_per_started_gameweek():
    inputs = league()
    frame = gameweek_expectations(inputs, [2, 3])
    assert set(frame["gw"]) == {2, 3}
    assert len(frame) == 2 * len(inputs.players)
    assert (frame["xpts"] >= 0).all() and frame["xpts"].sum() > 0


def test_expectations_only_use_earlier_data():
    inputs = league()
    before = gameweek_expectations(inputs, [3]).set_index("p_id")["xpts"]
    stats = inputs.stats.copy()
    stats.loc[stats["pg_gameweek"] >= 3, ["pg_xg", "pg_points"]] = [9.9, 30]  # GW3 itself and later
    after = gameweek_expectations(replace(inputs, stats=stats), [3]).set_index("p_id")["xpts"]
    assert list(before.round(6)) == list(after.round(6))


def test_started_gameweeks():
    inputs = league(n_played=4, n_future=5)
    assert started_gameweeks(inputs, 5) == [1, 2, 3, 4]
    assert started_gameweeks(inputs, None) == list(range(1, 10))
