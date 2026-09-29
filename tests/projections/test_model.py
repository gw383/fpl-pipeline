"""Tests for projections/model.py on a small synthetic league."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from league import TEAM_XG, league
from model import (
    ModelConfig,
    ModelInputs,
    _negbin_pmf,
    availability,
    fit_defcon_allowed,
    fit_team_ratings,
    goals_per_xg,
    goals_zero_prob,
    minutes_model,
    negbin_at_least,
    parse_return_date,
    poisson_expected_floor_div,
    project,
    relative_price,
    star_ratings,
    team_matches,
    team_price_priors,
)

# ---------------------------------------------------------------------------
# Poisson helpers
# ---------------------------------------------------------------------------


def test_negbin_at_least():
    mu = np.array([0.5, 2.0])
    poisson = 1 - np.exp(-mu) * (1 + mu)  # P(X >= 2) for a Poisson
    assert negbin_at_least(mu, 2, 1e7) == pytest.approx(poisson, rel=1e-4)  # k -> inf is Poisson
    # Extra spread: likelier to reach a threshold above the mean, less likely below it.
    assert negbin_at_least(np.array([6.0]), 10, 15.0)[0] > negbin_at_least(np.array([6.0]), 10, 1e7)[0]
    assert negbin_at_least(np.array([14.0]), 10, 15.0)[0] < negbin_at_least(np.array([14.0]), 10, 1e7)[0]


def test_expected_floor_division():
    assert poisson_expected_floor_div(np.array([0.0]), 3)[0] == pytest.approx(0.0, abs=1e-9)
    # For a large mean, E[floor(X/k)] ~ mu/k - (k-1)/(2k).
    assert poisson_expected_floor_div(np.array([30.0]), 3)[0] == pytest.approx(30 / 3 - 1 / 3, abs=0.05)


# ---------------------------------------------------------------------------
# Team ratings
# ---------------------------------------------------------------------------


def test_team_ratings_rank_attack_and_defence():
    inputs = league()
    ratings, league_avg = fit_team_ratings(team_matches(inputs, 5), TEAM_XG, 5, ModelConfig())
    ratings = ratings.set_index("team_id")
    assert ratings.loc[1, "attack"] > ratings.loc[4, "attack"]
    assert ratings.loc[4, "defence"] > ratings.loc[1, "defence"]  # 4 concedes more
    assert league_avg == pytest.approx(np.mean(list(TEAM_XG.values())), rel=0.2)


def test_team_ratings_shrink_towards_average():
    inputs = league()
    matches = team_matches(inputs, 5)
    weak, _ = fit_team_ratings(matches, TEAM_XG, 5, ModelConfig(team_prior_matches=0.5))
    strong, _ = fit_team_ratings(matches, TEAM_XG, 5, ModelConfig(team_prior_matches=50))
    spread = lambda r: r["attack"].max() - r["attack"].min()  # noqa: E731
    assert spread(strong) < spread(weak)


def test_no_history_means_average_teams():
    ratings, _ = fit_team_ratings(pd.DataFrame(), [1, 2], 1, ModelConfig())
    assert (ratings[["attack", "defence"]] == 1.0).all().all()


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------


def test_projection_ignores_the_future():
    inputs = league()
    before = project(inputs, 3).players.set_index("p_id")["xpts_horizon"]
    changed = inputs.stats.copy()
    changed.loc[changed["pg_gameweek"] >= 3, ["pg_xg", "pg_minutes"]] = [9.9, 0]
    after = project(ModelInputs(inputs.players, inputs.fixtures, inputs.gameweeks, changed), 3)
    pd.testing.assert_series_equal(before, after.players.set_index("p_id")["xpts_horizon"])


def test_forward_output_follows_team_strength():
    players = project(league(), 5).players.set_index("p_id")
    strong_forward, weak_forward = 4, 16  # team 1 vs team 4 forwards
    assert players.loc[strong_forward, "xpts_horizon"] > players.loc[weak_forward, "xpts_horizon"]


def test_home_fixture_is_easier_than_away():
    fixtures = project(league(), 5).fixtures
    forward = fixtures[fixtures["p_id"] == 8]  # team 2 forward
    by_venue = forward.groupby("is_home")["team_xg"].mean()
    assert by_venue[True] > by_venue[False]


def test_blank_and_double_gameweeks():
    # Team 1 gets an extra fixture in gameweek 5 (a double); nobody else does.
    inputs = league(extra_fixtures=[(5, 1, 2)])
    players = project(inputs, 5).players.set_index("p_id")
    doubled = project(league(), 5).players.set_index("p_id")
    assert players.loc[4, "xpts_next_gw"] > 1.6 * doubled.loc[4, "xpts_next_gw"]

    blank = league()
    fixtures = blank.fixtures[~((blank.fixtures["f_gameweek"] == 5) & (blank.fixtures["f_home_team"].isin([1, 4])))]
    fixtures = fixtures[~((fixtures["f_gameweek"] == 5) & (fixtures["f_away_team"].isin([1, 4])))]
    blanked = project(ModelInputs(blank.players, fixtures, blank.gameweeks, blank.stats), 5).players.set_index("p_id")
    assert blanked.loc[4, "xpts_next_gw"] == 0
    assert blanked.loc[4, "star"] < doubled.loc[4, "star"]


def test_summary_is_well_formed():
    players = project(league(), 5).players
    assert players["p_id"].is_unique
    assert players["star"].between(0, 10).all()
    assert (players["xpts_horizon"] >= players["xpts_next_gw"]).all()
    for position, group in players.groupby("p_position"):
        assert sorted(group["position_rank"]) == list(range(1, len(group) + 1)), position


def test_defensive_contribution_only_for_outfield_players():
    players = project(league(), 5).players.set_index("p_id")
    assert players.loc[1, "pts_defcon"] == 0  # goalkeeper
    assert players.loc[2, "pts_defcon"] > players.loc[3, "pts_defcon"]  # 8 actions/90 defender vs 3/90 midfielder


# ---------------------------------------------------------------------------
# Minutes and availability
# ---------------------------------------------------------------------------


def test_minutes_model_starts_and_benchings():
    inputs = league()
    stats = inputs.stats.copy()
    benched = stats["pg_id"] == 5
    stats.loc[benched, ["pg_minutes", "pg_starts"]] = 0  # never plays
    minutes = minutes_model(ModelInputs(inputs.players, inputs.fixtures, inputs.gameweeks, stats), 5, ModelConfig())
    minutes = minutes.set_index("p_id")
    assert minutes.loc[1, "p_start"] == pytest.approx(ModelConfig().start_prob_cap)
    assert minutes.loc[5, "p_start"] == 0 and minutes.loc[5, "p_sub"] == 0


def _horizon() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "gw": [6, 7, 8],
            "gw_index": [0, 1, 2],
            "deadline": pd.to_datetime(["2026-10-03", "2026-10-17", "2026-10-24"], utc=True),
        }
    )


def test_availability_rules():
    players = pd.DataFrame(
        [
            (1, "a", np.nan, ""),
            (2, "d", 75.0, "Knock - 75% chance of playing"),
            (3, "u", 0.0, "Has joined another club"),
            (4, "i", 0.0, "Hamstring injury - Expected back 20 Oct"),
        ],
        columns=["p_id", "p_status", "p_chance_of_playing", "p_news"],
    )
    result = availability(players, _horizon(), ModelConfig()).pivot(index="p_id", columns="gw", values="availability")
    assert list(result.loc[1]) == [1.0, 1.0, 1.0]
    assert result.loc[2, 6] == 0.75 and result.loc[2, 7] == pytest.approx(0.875)
    assert list(result.loc[3]) == [0.0, 0.0, 0.0]
    assert list(result.loc[4]) == [0.0, 0.0, 1.0]  # back after the 17 Oct deadline

    ignored = availability(players, _horizon(), ModelConfig(use_availability=False))
    assert (ignored["availability"] == 1.0).all()


@pytest.mark.parametrize(
    ("news", "reference", "expected"),
    [
        ("Hamstring injury - Expected back 18 Oct", date(2026, 10, 1), date(2026, 10, 18)),
        ("Suspended until 04 Jan", date(2026, 12, 20), date(2027, 1, 4)),
        ("Knee injury - Unknown return date", date(2026, 10, 1), None),
        (None, date(2026, 10, 1), None),
    ],
)
def test_parse_return_date(news, reference, expected):
    assert parse_return_date(news, reference) == expected


# ---------------------------------------------------------------------------
# Star rating
# ---------------------------------------------------------------------------


def test_star_scale_is_relative_to_the_week():
    xpts = pd.Series([6.0, 5.0, 4.0, 3.0, 3.0, 2.0, 0.5, 0.0])
    xmins = pd.Series([90, 90, 90, 90, 90, 90, 10, 0])
    stars, typical, best = star_ratings(xpts, xmins, ModelConfig())
    assert typical == pytest.approx(3.5)  # median of the six regulars
    assert best == 6.0 and stars.iloc[0] == 10.0
    assert stars.iloc[1] == pytest.approx(5 + 5 * 1.5 / 2.5)
    assert stars.iloc[-1] == 0.0  # clamped
    assert stars.between(0, 10).all()


def test_star_scale_without_regulars_falls_back_gracefully():
    stars, _, _ = star_ratings(pd.Series([0.0, 0.0]), pd.Series([0.0, 0.0]), ModelConfig())
    assert (stars == 0).all()


def test_new_signings_are_judged_from_their_debut():
    inputs = league()
    stats = inputs.stats.copy()
    # Player 5 (team 2's keeper) only appears from GW3, unused that week, then starts GW4.
    stats = stats[~((stats["pg_id"] == 5) & (stats["pg_gameweek"] < 3))]
    stats.loc[(stats["pg_id"] == 5) & (stats["pg_gameweek"] == 3), ["pg_minutes", "pg_starts"]] = 0
    # Player 6 was there from GW1 but unused until GW4: those weeks do count.
    stats.loc[(stats["pg_id"] == 6) & (stats["pg_gameweek"] < 4), ["pg_minutes", "pg_starts"]] = 0
    minutes = minutes_model(ModelInputs(inputs.players, inputs.fixtures, inputs.gameweeks, stats), 5, ModelConfig())
    minutes = minutes.set_index("p_id")
    assert minutes.loc[5, "p_start"] == pytest.approx(ModelConfig().start_prob_cap)
    assert minutes.loc[6, "p_start"] < 0.7


# ---------------------------------------------------------------------------
# Goals distribution and calibration
# ---------------------------------------------------------------------------


def test_negative_binomial_clean_sheets():
    mu = np.array([0.5, 1.5, 2.5])
    assert (goals_zero_prob(mu, 6.0) > np.exp(-mu)).all()  # uncertainty makes 0-0s likelier
    assert goals_zero_prob(mu, 1e7) == pytest.approx(np.exp(-mu), rel=1e-4)  # k -> inf is Poisson
    pmf = _negbin_pmf(mu, 6.0)
    assert pmf.sum(axis=1) == pytest.approx(1.0)
    assert (pmf * np.arange(pmf.shape[1])).sum(axis=1) == pytest.approx(mu)


def test_goals_per_xg_is_shrunk_towards_one():
    inputs = league()
    stats = inputs.stats.assign(pg_goals=0)  # nobody has scored from plenty of xG
    ratio = goals_per_xg(ModelInputs(inputs.players, inputs.fixtures, inputs.gameweeks, stats), 5, ModelConfig())
    assert 0.5 < ratio < 1.0


# ---------------------------------------------------------------------------
# Defensive contribution
# ---------------------------------------------------------------------------


def _defcon_matches() -> pd.DataFrame:
    """Four teams, everyone plays everyone home and away; teams make 60
    defensive actions a match, except 90 against team 4."""
    rows = []
    pairs = [(a, b) for a in range(1, 5) for b in range(1, 5) if a != b]
    for gw, (home, away) in enumerate(pairs, start=1):
        for team, opponent in ((home, away), (away, home)):
            rows.append((gw, gw, team, opponent, 90.0 if opponent == 4 else 60.0))
    return pd.DataFrame(rows, columns=["f_id", "gw", "team_id", "opponent_id", "defcons"])


def test_defcon_allowed_finds_the_generous_opponent():
    matches = _defcon_matches()
    allowed = fit_defcon_allowed(matches, [1, 2, 3, 4], 13, ModelConfig(defcon_prior_matches=0.01))
    assert allowed[4] > 1.2
    assert allowed[[1, 2, 3]].max() < 1.0
    shrunk = fit_defcon_allowed(matches, [1, 2, 3, 4], 13, ModelConfig(defcon_prior_matches=20))
    assert 1.0 < shrunk[4] < allowed[4]
    off = fit_defcon_allowed(matches, [1, 2, 3, 4], 13, ModelConfig(use_defcon_opponent=False))
    assert (off == 1.0).all()


def test_defcon_points_follow_the_opponent():
    inputs = league()
    fixtures = inputs.fixtures
    # Everyone makes 50% more defensive actions against team 4.
    against_4 = pd.concat(
        [
            fixtures.loc[fixtures["f_away_team"] == 4, ["f_gameweek", "f_home_team"]].set_axis(["gw", "team"], axis=1),
            fixtures.loc[fixtures["f_home_team"] == 4, ["f_gameweek", "f_away_team"]].set_axis(["gw", "team"], axis=1),
        ]
    )
    stats = inputs.stats.merge(inputs.players[["p_id", "p_team"]], left_on="pg_id", right_on="p_id")
    hit = stats.set_index(["pg_gameweek", "p_team"]).index.isin(against_4.set_index(["gw", "team"]).index)
    stats.loc[hit, "pg_defcons"] *= 1.5
    stats = stats.drop(columns=["p_id", "p_team"])

    projection = project(ModelInputs(inputs.players, fixtures, inputs.gameweeks, stats), 5)
    allowed = projection.teams.set_index("team_id")["defcon_allowed_index"]
    assert allowed[4] > 1.05 and allowed[4] == allowed.max()
    defender = projection.fixtures[(projection.fixtures["p_id"] == 2)]  # team 1's defender
    by_opponent = defender.groupby("opponent_id")["pts_defcon"].mean()
    assert by_opponent[4] == by_opponent.max()


# ---------------------------------------------------------------------------
# Prices as a prior
# ---------------------------------------------------------------------------


def _priced(inputs: ModelInputs, prices: dict[int, float] | None = None, default: float = 5.0) -> ModelInputs:
    players = inputs.players.assign(p_start_price=default)
    for p_id, price in (prices or {}).items():
        players.loc[players["p_id"] == p_id, "p_start_price"] = price
    return ModelInputs(players, inputs.fixtures, inputs.gameweeks, inputs.stats, inputs.penalties)


def test_equal_prices_change_nothing():
    inputs = league()
    before = project(inputs, 5).players.set_index("p_id")["xpts_horizon"]
    after = project(_priced(inputs), 5).players.set_index("p_id")["xpts_horizon"]
    assert list(after.round(6)) == list(before.round(6))


def test_expensive_player_is_pulled_towards_more():
    inputs = league()
    cheap = project(_priced(inputs), 5).players.set_index("p_id")
    dear = project(_priced(inputs, {4: 10.0}), 5).players.set_index("p_id")
    assert dear.loc[4, "xg_p90"] > cheap.loc[4, "xg_p90"]
    assert dear.loc[4, "xpts_horizon"] > cheap.loc[4, "xpts_horizon"]
    off = project(_priced(inputs, {4: 10.0}), 5, ModelConfig(price_prior_power=0, team_price_prior_power=0))
    assert off.players.set_index("p_id").loc[4, "xg_p90"] == pytest.approx(cheap.loc[4, "xg_p90"])


def test_price_helpers():
    players = pd.DataFrame(
        {"p_id": [1, 2, 3], "p_team": [1, 1, 2], "p_position": [3, 3, 3], "p_start_price": [10.0, 5.0, np.nan]}
    ).assign(p_price=[10.5, 5.0, 6.0])
    relative = relative_price(players, ModelConfig(price_prior_power=1.0))
    assert relative[1] > 1 > relative[2]  # the missing start price falls back to the current price
    assert (relative_price(players.drop(columns=["p_start_price", "p_price"]), ModelConfig()) == 1.0).all()
    attack, defence = team_price_priors(players, [1, 2, 3], ModelConfig())
    assert attack[3] == 1.0 and defence[3] == 1.0  # no players, no information
    assert team_price_priors(players, [1, 2], ModelConfig(team_price_prior_power=0)) is None
