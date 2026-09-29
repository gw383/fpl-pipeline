"""Tests for projections/backtest.py."""

import pandas as pd
import pytest

from backtest import METHODS, backtest, baselines, default_targets
from league import league
from model import ModelInputs


def test_baselines_are_points_per_team_match():
    inputs = league()
    stats = inputs.stats.copy()
    stats.loc[stats["pg_id"] == 4, "pg_points"] = [2, 4, 6, 8]  # gameweeks 1-4
    frame = baselines(ModelInputs(inputs.players, inputs.fixtures, inputs.gameweeks, stats), 5).set_index("p_id")
    assert frame.loc[4, "season"] == pytest.approx(5.0)
    assert frame.loc[4, "form"] == pytest.approx(5.0)  # all four gameweeks are in the window


def test_backtest_scores_every_method():
    inputs = league()
    targets = default_targets(inputs)
    assert targets == [2, 3, 4]
    metrics, predictions = backtest(inputs, targets)
    assert list(metrics.index) == METHODS
    assert set(predictions["gw"]) == set(targets)
    assert metrics["MAE"].notna().all()


def test_no_target_without_history():
    inputs = league(n_played=1)
    assert default_targets(inputs) == []
    assert isinstance(inputs.stats, pd.DataFrame)
