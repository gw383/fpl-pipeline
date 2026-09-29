"""Tests for the previous-seasons prior (history_rates and its use in the
player rates)."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from league import league
from model import ModelConfig, history_rates, project

COLUMNS = [
    "p_id", "ps_season", "ps_seasons_ago", "ps_minutes", "ps_goals", "ps_assists", "ps_clean_sheets",
    "ps_goals_conceded", "ps_saves", "ps_bps", "ps_yellow_cards", "ps_xg", "ps_xa", "ps_defensive_contribution",
    "ps_cbi", "ps_tackles", "ps_recoveries", "ps_penalties_missed", "ps_penalties_taken", "ps_team_join_date",
]  # fmt: skip


def season(p_id, ago, minutes=2700, xg=6.0, pens=0, cbi=None, tackles=None, recoveries=None, dc=None, joined=None):
    """One history row (30 full games by default)."""
    return (
        p_id, f"{2026 - ago}-{str(2027 - ago)[-2:]}", ago, minutes, 3, 2, 5, 30, 0, 600, 3,
        xg, 3.0, dc, cbi, tackles, recoveries, 0, pens, joined,
    )  # fmt: skip


def with_history(rows):
    inputs = league()
    return replace(inputs, history=pd.DataFrame(rows, columns=COLUMNS))


def test_penalties_come_out_of_past_xg():
    inputs = with_history([season(4, 1, xg=9.0, pens=5)])
    rates = history_rates(inputs, ModelConfig()).set_index("p_id")
    open_play = 9.0 - 5 * ModelConfig().penalty_xg
    assert rates.loc[4, "xg_hist"] == pytest.approx(open_play / 30)
    assert rates.loc[4, "xg_hist_90s"] == pytest.approx(30)


def test_seasons_are_weighted_and_old_ones_ignored():
    inputs = with_history([season(4, 1, xg=3.0), season(4, 2, xg=9.0), season(4, 3, xg=30.0)])
    rates = history_rates(inputs, ModelConfig(history_season_weights=(1.0, 0.5))).set_index("p_id")
    default = history_rates(inputs, ModelConfig()).set_index("p_id")
    assert default.loc[4, "xg_hist"] == pytest.approx(3.0 / 30)  # last season only by default
    # Last season (weight 1) and the one before (0.5); three seasons ago is ignored.
    assert rates.loc[4, "xg_hist"] == pytest.approx((3.0 + 0.5 * 9.0) / (30 + 0.5 * 30))
    assert rates.loc[4, "xg_hist_90s"] == pytest.approx(45)


def test_defensive_actions_follow_the_current_position():
    # Player 2 is a defender, player 3 a midfielder: same past counts.
    rows = [season(p, 1, cbi=150.0, tackles=60.0, recoveries=90.0) for p in (2, 3)]
    rows.append(season(6, 1, dc=240.0))  # a season with only the total
    rates = history_rates(with_history(rows), ModelConfig()).set_index("p_id")
    assert rates.loc[2, "defcons_hist"] == pytest.approx(210 / 30)  # CBI + tackles
    assert rates.loc[3, "defcons_hist"] == pytest.approx(300 / 30)  # + recoveries
    assert rates.loc[6, "defcons_hist"] == pytest.approx(240 / 30)


def test_summer_signings_count_for_less():
    rows = [season(4, 1), season(8, 1, joined="2026-07-20T00:00:00Z")]
    rates = history_rates(with_history(rows), ModelConfig()).set_index("p_id")
    assert rates.loc[8, "xg_hist_90s"] == pytest.approx(ModelConfig().history_mover_weight * 30)
    assert rates.loc[4, "xg_hist_90s"] == pytest.approx(30)


def test_no_history_means_price_only_priors():
    inputs = league()
    assert history_rates(inputs, ModelConfig()).empty
    before = project(inputs, 5).players.set_index("p_id")["xpts_horizon"]
    off = project(with_history([season(4, 1, xg=30.0)]), 5, ModelConfig(use_history=False))
    assert list(off.players.set_index("p_id")["xpts_horizon"].round(6)) == list(before.round(6))


def test_history_pulls_rates_and_fades_as_the_season_goes_on():
    # Forward 4 averaged 1.8 xG per 90 last season, more than this season so far.
    inputs = with_history([season(4, 1, xg=54.0)])
    base = project(league(), 5).players.set_index("p_id")
    boosted = project(inputs, 5).players.set_index("p_id")
    assert boosted.loc[4, "xg_p90"] > base.loc[4, "xg_p90"]
    no_fade = project(inputs, 5, ModelConfig(history_fade=1.0)).players.set_index("p_id")
    assert base.loc[4, "xg_p90"] < boosted.loc[4, "xg_p90"] < no_fade.loc[4, "xg_p90"]


def test_a_breakout_wins_through():
    # A forward who did little last season: the more of this season he has
    # played, the closer his rate gets to this season's numbers.
    inputs = with_history([season(16, 1, xg=1.0)])
    this_season = {}
    for gw in (3, 5):
        players = project(inputs, gw).players.set_index("p_id")
        plain = project(league(), gw).players.set_index("p_id")
        this_season[gw] = players.loc[16, "xg_p90"] / plain.loc[16, "xg_p90"]
    assert this_season[3] < this_season[5] < 1.0
    assert np.isfinite(list(this_season.values())).all()
