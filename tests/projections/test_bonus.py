"""Bonus is projected from BPS: a base BPS rate plus the BPS from each
fixture's expected goals, assists, clean sheets and saves, turned into
expected bonus with a learned BPS -> bonus curve and scaled so each match
hands out its usual total."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from league import league
from model import DEFAULT_BONUS_PER_MATCH, ModelConfig, bonus_model, event_bps, project


def test_event_bps_uses_the_bps_values_for_each_position():
    rows = pd.DataFrame(
        {
            "p_position": [1, 2, 3, 4],
            "pg_goals": [0, 1, 1, 2],
            "pg_assists": [0, 0, 1, 0],
            "pg_clean_sheets": [1, 1, 1, 0],
            "pg_goals_conceded": [0, 0, 0, 3],
            "pg_saves": [4, 0, 0, 0],
            "pg_pens_missed": [0, 0, 0, 1],
        }
    )
    # GK: CS 12 + 4 saves x 2; DEF: goal 12 + CS 12; MID: goal 18 + assist 9 (no CS BPS);
    # FWD: 2 goals x 24, conceded doesn't count for forwards, missed penalty -6.
    assert event_bps(rows).tolist() == [20, 24, 27, 42]


def test_default_curve_until_there_is_enough_data():
    model = bonus_model(league(), 5, ModelConfig())
    assert model.bonus[0] == 0 and model.bonus[-1] == 3.0
    assert model.base_sd == ModelConfig().default_base_bps_sd
    assert model.per_match == DEFAULT_BONUS_PER_MATCH


def test_learned_curve_is_non_decreasing():
    inputs = league()
    rng = np.random.default_rng(0)
    stats = inputs.stats.copy()
    many = pd.concat([stats] * 8, ignore_index=True)  # 512 rows of 90-minute appearances
    many["pg_bps"] = rng.integers(0, 50, len(many))
    many["pg_bonus"] = np.where(many["pg_bps"] > 30, 3, np.where(many["pg_bps"] > 25, rng.integers(0, 2, len(many)), 0))
    model = bonus_model(replace(inputs, stats=many), 5, ModelConfig())
    assert (np.diff(model.bonus) >= -1e-12).all()
    assert model.bonus[0] == 0 and model.bonus[-1] == 3


def test_each_fixture_shares_the_usual_bonus_total():
    fixtures = project(league(), 5).fixtures
    per_fixture = fixtures.groupby("f_id")["pts_bonus"].sum()
    assert per_fixture.to_numpy() == pytest.approx(DEFAULT_BONUS_PER_MATCH)


def test_higher_base_bps_means_more_bonus():
    inputs = league()
    stats = inputs.stats.copy()
    stats.loc[stats["pg_id"] == 3, "pg_bps"] += 12  # team 1's midfielder racks up BPS
    players = project(replace(inputs, stats=stats), 5).players.set_index("p_id")
    baseline = project(inputs, 5).players.set_index("p_id")
    assert players.loc[3, "pts_bonus"] > baseline.loc[3, "pts_bonus"]


def test_attackers_get_more_bonus_in_easier_fixtures():
    fixtures = project(league(), 5).fixtures
    forward = fixtures[fixtures["p_id"] == 8].sort_values("team_xg")  # team 2's forward
    # Bonus share rises with how many goals his team is expected to score.
    assert forward["pts_bonus"].iloc[-1] >= forward["pts_bonus"].iloc[0]
