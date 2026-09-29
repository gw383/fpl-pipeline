"""Penalties are modelled as a role: taken out of open-play xG, then
projected separately for the designated takers."""

from dataclasses import replace

import pandas as pd
import pytest

from league import league
from model import ModelConfig, league_penalty_rate, open_play_inputs, project

NO_PENALTIES_YET = pd.DataFrame(columns=["p_id", "gw_id", "penalties_taken"])


def _with_orders(inputs, orders: dict[int, int], penalties=NO_PENALTIES_YET):
    players = inputs.players.assign(p_penalties_order=inputs.players["p_id"].map(orders))
    return replace(inputs, players=players, penalties=penalties)


def test_penalty_xg_is_removed_from_history():
    inputs = league()
    penalties = pd.DataFrame({"p_id": [4], "gw_id": [2], "penalties_taken": [1]})
    open_play = open_play_inputs(replace(inputs, penalties=penalties), ModelConfig()).stats
    before = inputs.stats.set_index(["pg_id", "pg_gameweek"])["pg_xg"]
    after = open_play.set_index(["pg_id", "pg_gameweek"])["pg_xg"]
    assert after[(4, 2)] == pytest.approx(before[(4, 2)] - 0.79)
    assert after.drop((4, 2)).equals(before.drop((4, 2)))


def test_without_penalty_data_nothing_changes():
    fixtures = project(league(), 5).fixtures
    assert (fixtures["xpens"] == 0).all() and (fixtures["pts_penalties"] == 0).all()


def test_first_choice_taker_gets_most_penalties():
    inputs = _with_orders(league(), {4: 1, 3: 2})  # team 1: forward first, midfielder second
    fixtures = project(inputs, 5).fixtures
    team1 = fixtures[fixtures["team_id"] == 1].groupby("p_id")["xpens"].sum()
    assert team1[4] > team1[3] > 0
    assert team1.drop([3, 4]).sum() == 0  # no order, no penalties


def test_penalties_pass_to_the_next_taker_when_first_choice_is_out():
    inputs = _with_orders(league(), {4: 1, 3: 2})
    out = inputs.players.copy()
    out.loc[out["p_id"] == 4, "p_status"] = "u"  # first choice has left the club
    fixtures = project(replace(inputs, players=out), 5).fixtures
    team1 = fixtures[fixtures["team_id"] == 1].groupby("p_id")["xpens"].sum()
    assert team1[4] == 0 and team1[3] > 0


def test_taker_shares_never_exceed_the_team_total():
    inputs = _with_orders(league(), {4: 1, 3: 2, 2: 3})
    fixtures = project(inputs, 5).fixtures
    team1 = fixtures[fixtures["team_id"] == 1]
    per_fixture = team1.groupby("f_id")["xpens"].sum()
    rate = league_penalty_rate(inputs, 5, ModelConfig())
    assert (per_fixture > 0).all()
    assert (per_fixture <= rate * 3).all()  # generous upper bound on any team's expected penalties


def test_lucky_penalties_no_longer_inflate_a_non_taker():
    # Team 2's forward (id 8) scored a penalty every week but isn't on penalties now.
    penalties = pd.DataFrame({"p_id": [8] * 4, "gw_id": [1, 2, 3, 4], "penalties_taken": [1] * 4})
    baseline = project(_with_orders(league(), {}, penalties=None), 5).players.set_index("p_id")
    split = project(_with_orders(league(), {}, penalties=penalties), 5).players.set_index("p_id")
    assert split.loc[8, "xg_horizon"] < baseline.loc[8, "xg_horizon"]
    assert split.loc[8, "xpens_horizon"] == 0


def test_penalty_points_count_goals_and_misses():
    inputs = _with_orders(league(), {4: 1})
    fixtures = project(inputs, 5).fixtures
    taker = fixtures[fixtures["p_id"] == 4]
    cfg = ModelConfig()
    per_penalty = cfg.penalty_conversion * 4 + (1 - cfg.penalty_conversion) * -2  # forward: 4 points a goal
    assert taker["pts_penalties"].tolist() == pytest.approx((taker["xpens"] * per_penalty).tolist())
    assert (taker["xpens"] > 0).all()


def test_league_rate_is_shrunk_towards_the_long_run_rate():
    inputs = league()
    cfg = ModelConfig()
    none_taken = league_penalty_rate(replace(inputs, penalties=NO_PENALTIES_YET), 5, cfg)
    many = pd.DataFrame({"p_id": [4] * 4, "gw_id": [1, 2, 3, 4], "penalties_taken": [3] * 4})
    lots = league_penalty_rate(replace(inputs, penalties=many), 5, cfg)
    assert none_taken < cfg.penalty_rate_prior < lots
