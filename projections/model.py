"""Expected-points projection model.

For every player and every fixture in the next few gameweeks the model
predicts how many FPL points he will score, by modelling each way of
scoring separately:

    expected points = appearance + goals + assists + penalties + clean sheet
                      + goals conceded + saves + defensive contribution
                      + bonus + cards

Each piece is built from three smaller models:

* **Team ratings** -- an attack and a defence multiplier per team, fitted to
  every match's xG (for and against), adjusted for who each side has played
  and for home advantage, and shrunk towards the league average so a handful
  of games can't produce an extreme rating.
* **Player rates** -- recency-weighted xG, xA, defensive actions, saves,
  "base" BPS and cards per 90, adjusted for the opponents faced and shrunk towards
  the position average when the player has few minutes.
* **Minutes** -- how likely the player is to start, come off the bench or
  play 60+ minutes, from recent team selections and FPL's availability flags.
* **Penalties** -- treated as a role, not as chance creation. Penalty xG is
  taken out of every player's (and team's) history, so the rates above are
  open play only; penalties are then projected separately: how many the team
  should win, times the chance each designated taker (FPL's penalty order)
  is on the pitch to take them.

A fixture's expected points then follow directly: e.g. expected goals =
player xG per 90 x expected minutes / 90 x how leaky this opponent is at this
venue. Blank and double gameweeks need no special handling -- a player simply
has zero, one or two fixtures in a gameweek.

Because the output is in FPL points, it can be checked against what actually
happened (see backtest.py). Everything here is plain pandas/numpy with no
database access, so the same code serves the live run and the backtest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# FPL scoring rules (positions: 1 GK, 2 DEF, 3 MID, 4 FWD)
# ---------------------------------------------------------------------------

GOAL_POINTS = {1: 10, 2: 6, 3: 5, 4: 4}
ASSIST_POINTS = 3
CLEAN_SHEET_POINTS = {1: 4, 2: 4, 3: 1, 4: 0}
GOALS_CONCEDED_PER_POINT = 2  # GK/DEF lose 1 point per 2 conceded
SAVES_PER_POINT = 3  # GK gains 1 point per 3 saves
DEFCON_THRESHOLD = {2: 10, 3: 12, 4: 12}  # defensive actions for the bonus
DEFCON_POINTS = 2
PENALTY_MISS_POINTS = -2

# Bonus Points System values for the events the model projects per fixture
# (everything else a player does -- passes, tackles, recoveries, minutes --
# is his "base" BPS). Bonus goes to the match's top three BPS scores.
BPS_GOAL = {1: 12, 2: 12, 3: 18, 4: 24}
BPS_ASSIST = 9
BPS_CLEAN_SHEET = 12  # GK/DEF
BPS_GOAL_CONCEDED = -4  # GK/DEF, per goal
BPS_SAVE = 2  # GK, per save
BPS_PENALTY_MISS = -6

# Fallback BPS -> expected bonus curve (used before a season has enough data),
# shaped like the empirical one: nothing below ~20 BPS, about 1 bonus point
# at ~28, nearly 3 from ~45.
DEFAULT_BONUS_PER_MATCH = 6.3
DEFAULT_BONUS_CURVE = (
    (0, 0.0),
    (20, 0.0),
    (24, 0.15),
    (28, 1.0),
    (32, 1.4),
    (36, 2.0),
    (40, 2.5),
    (48, 2.9),
    (80, 3.0),
)

POSITIONS = (1, 2, 3, 4)


@dataclass(frozen=True)
class ModelConfig:
    """Every tunable in one place. Defaults are sensible starting values;
    backtest.py measures how well they predict."""

    horizon: int = 5  # gameweeks projected ahead

    # Recency: weight = decay ** gameweeks_ago.
    form_decay: float = 0.90  # player per-90 rates
    team_decay: float = 0.93  # team ratings (change more slowly)
    minutes_decay: float = 0.60  # team selection (last game matters most)

    # Shrinkage: evidence is blended with this much "average" data.
    team_prior_matches: float = 4.0
    rate_prior_90s: dict[str, float] = field(
        default_factory=lambda: {"xg": 2.0, "xa": 2.0, "defcons": 1.0, "saves": 1.5, "base_bps": 3.0, "yellow": 4.0}
    )

    # xG multiplier for the home side; the away side gets its reciprocal.
    home_advantage: float = 1.12

    # Minutes model.
    start_prob_cap: float = 0.95  # even ever-presents get rotated or injured
    default_minutes_if_start: float = 80.0
    default_minutes_if_sub: float = 20.0
    default_p60_given_start: float = 0.85

    # Availability: a flagged player's chance of playing recovers by this
    # share of the remaining gap per gameweek when FPL gives no return date.
    recovery_per_gameweek: float = 0.5
    flagged_default_chance: float = 0.5

    # Bonus: the BPS -> expected bonus curve is learned from this season's
    # 60+ minute appearances once there are this many of them.
    bonus_curve_min_rows: int = 300
    default_base_bps_sd: float = 5.0

    # Star rating is relative to the week: a typical regular starter (expected
    # to average at least this many minutes a gameweek) scores 5, the best
    # projection 10.
    star_regular_minutes: float = 60.0

    # Penalties. Opta (and so FPL) values every penalty at about 0.79 xG;
    # roughly 78% are scored. The league's penalty rate is shrunk towards the
    # long-run Premier League figure of about 0.14 per team per match.
    penalty_xg: float = 0.79
    penalty_conversion: float = 0.78
    penalty_rate_prior: float = 0.14
    penalty_prior_matches: float = 100.0
    use_penalties: bool = True

    # Goals from expected goals. Goals conceded follow a negative binomial,
    # not a Poisson: the model's expected goals for a match are an estimate,
    # and that uncertainty makes 0-0s (clean sheets) more likely than a
    # Poisson with the same mean says. And expected goals are scaled by how
    # many goals xG has actually turned into this season, shrunk towards
    # 1:1 with this much xG's worth of prior (a few hundred shots).
    goals_dispersion: float = 6.0
    goals_per_xg_prior: float = 150.0

    # Defensive contribution. Some opponents give away more defensive actions
    # than others; each team gets a multiplier for how many defensive actions
    # defenders and midfielders make against it, shrunk towards 1.0 by this
    # many matches of average. Actions in a match follow a negative binomial
    # with this dispersion (a Poisson whose rate is itself uncertain).
    defcon_prior_matches: float = 4.0
    defcon_dispersion: float = 15.0
    use_defcon_opponent: bool = True

    # Prices as a prior. FPL's start-of-season prices sum up what's known
    # about players and teams from previous seasons. Instead of shrinking
    # towards a plain average, player xG, xA and base BPS are shrunk towards
    # the position average x (his price / the position's average price) **
    # price_prior_power, and team ratings towards (the squad's price / the
    # league's) ** team_price_prior_power. 0 turns either off.
    price_prior_power: float = 1.0
    team_price_prior_power: float = 1.0

    # Previous seasons as a prior (FPL's history_past). A player's per-90
    # rates from last season (seasons further back can be added with
    # history_season_weights, e.g. (1.0, 0.5); the backtest preferred last
    # season alone)
    # replace the price-based prior, in proportion to how many past 90s back
    # them up: trust = past 90s / (past 90s + history_confidence_90s). They
    # then count as extra 90s in the shrinkage -- up to history_prior_90s at
    # the start of the season, fading by history_fade per gameweek played, so
    # this season's evidence takes over as it builds (and a genuine breakout
    # wins through). A player who changed club over the summer has his past
    # 90s counted at history_mover_weight.
    history_prior_90s: float = 8.0
    history_confidence_90s: float = 15.0
    history_season_weights: tuple[float, ...] = (1.0,)
    history_fade: float = 0.95
    history_mover_weight: float = 0.5
    use_history: bool = True

    # Apply FPL's current availability flags (the backtest turns this off,
    # because past flags aren't stored).
    use_availability: bool = True

    def with_overrides(self, **kwargs) -> ModelConfig:
        return replace(self, **kwargs)


@dataclass(frozen=True)
class ModelInputs:
    """The four analytics tables the model needs (lower-case column names).

    players:   p_id, p_team, p_position, p_status, p_chance_of_playing, p_news
               (optionally p_penalties_order: 1 = first-choice taker, and
               p_start_price / p_price for the price priors)
    fixtures:  f_id, f_gameweek, f_home_team, f_away_team
    gameweeks: gw_id, gw_deadline_time
    stats:     pg_id, pg_gameweek, pg_minutes, pg_starts, pg_xg, pg_xa,
               pg_defcons, pg_saves, pg_bonus, pg_yellow_cards, pg_points, pg_bps,
               pg_goals, pg_assists, pg_clean_sheets, pg_goals_conceded,
               pg_pens_missed
    penalties: p_id, gw_id, penalties_taken -- or None if penalty data is
               unavailable, in which case the model uses raw xG (penalties
               included) and doesn't project penalties separately.
    history:   previous Premier League seasons (analytics.player_past_seasons,
               ps_* columns) -- or None, in which case priors come from
               prices only.
    """

    players: pd.DataFrame
    fixtures: pd.DataFrame
    gameweeks: pd.DataFrame
    stats: pd.DataFrame
    penalties: pd.DataFrame | None = None
    history: pd.DataFrame | None = None


@dataclass(frozen=True)
class Projection:
    """Model output: one row per player per upcoming fixture, one row per
    player, and one row per team."""

    fixtures: pd.DataFrame
    players: pd.DataFrame
    teams: pd.DataFrame
    as_of_gw: int
    horizon_gws: list[int]


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------

_POISSON_TERMS = np.arange(0, 80)
_LOG_FACTORIALS = np.cumsum(np.log(np.maximum(_POISSON_TERMS, 1)))


def _poisson_pmf(mu: np.ndarray) -> np.ndarray:
    """P(X = k) for k = 0..79, one row per mean."""
    mu = np.clip(np.asarray(mu, dtype=float), 1e-12, None)[:, None]
    return np.exp(_POISSON_TERMS * np.log(mu) - mu - _LOG_FACTORIALS)


def _negbin_pmf(mu, k: float) -> np.ndarray:
    """P(X = n) for n = 0..79 under a negative binomial with mean ``mu`` and
    dispersion ``k`` (a Poisson whose rate is itself uncertain; k -> infinity
    is plain Poisson), one row per mean."""
    mu = np.clip(np.asarray(mu, dtype=float), 0.0, None)[:, None]
    q = mu / (k + mu)
    pmf = np.empty((mu.shape[0], len(_POISSON_TERMS)))
    pmf[:, 0] = ((k / (k + mu)) ** k)[:, 0]
    for n in range(1, len(_POISSON_TERMS)):
        pmf[:, n] = pmf[:, n - 1] * (n - 1 + k) / n * q[:, 0]
    return pmf


def negbin_at_least(mu, threshold: int, k: float) -> np.ndarray:
    """P(X >= threshold) under the negative binomial above -- e.g. the chance
    of reaching the defensive-contribution threshold."""
    return 1.0 - _negbin_pmf(mu, k)[:, :threshold].sum(axis=1)


def goals_zero_prob(mu, k: float) -> np.ndarray:
    """P(no goals) when goals have mean ``mu`` -- the clean-sheet chance."""
    mu = np.clip(np.asarray(mu, dtype=float), 0.0, None)
    return (1.0 + mu / k) ** (-k)


def goals_expected_floor_div(mu, divisor: int, k: float) -> np.ndarray:
    """E[floor(goals / divisor)] under the same negative binomial, e.g. the
    goals-conceded deduction (one point per two)."""
    return (_negbin_pmf(mu, k) * (_POISSON_TERMS // divisor)).sum(axis=1)


def poisson_expected_floor_div(mu, divisor: int) -> np.ndarray:
    """E[floor(X / divisor)] for X ~ Poisson(mu) -- e.g. expected save points
    (one per three saves) or goals-conceded deductions (one per two)."""
    return (_poisson_pmf(mu) * (_POISSON_TERMS // divisor)).sum(axis=1)


def _venue(is_home: pd.Series, home_advantage: float) -> pd.Series:
    return np.where(is_home, home_advantage, 1.0 / home_advantage)


# ---------------------------------------------------------------------------
# Time windows
# ---------------------------------------------------------------------------


def next_gameweek(gameweeks: pd.DataFrame, now: datetime) -> int | None:
    """The first gameweek whose deadline is still ahead."""
    deadlines = pd.to_datetime(gameweeks["gw_deadline_time"], utc=True)
    upcoming = gameweeks.loc[deadlines > pd.Timestamp(now).tz_convert("UTC"), "gw_id"]
    return int(upcoming.min()) if not upcoming.empty else None


def _history(inputs: ModelInputs, as_of_gw: int) -> pd.DataFrame:
    """Player stats from before ``as_of_gw`` only -- nothing from the future."""
    return inputs.stats[inputs.stats["pg_gameweek"] < as_of_gw]


def _team_fixtures(fixtures: pd.DataFrame) -> pd.DataFrame:
    """Every fixture twice, once from each side: team, opponent, venue."""
    fixtures = fixtures.dropna(subset=["f_gameweek"])
    home = fixtures.assign(team_id=fixtures["f_home_team"], opponent_id=fixtures["f_away_team"], is_home=True)
    away = fixtures.assign(team_id=fixtures["f_away_team"], opponent_id=fixtures["f_home_team"], is_home=False)
    out = pd.concat([home, away], ignore_index=True)
    out["gw"] = out["f_gameweek"].astype(int)
    return out[["f_id", "gw", "team_id", "opponent_id", "is_home"]]


# ---------------------------------------------------------------------------
# Prices as a prior
# ---------------------------------------------------------------------------

PRICE_PRIOR_STATS = ("xg", "xa", "base_bps")
TEAM_ATTACK_PRICE_PLAYERS = 6  # a team's six most expensive midfielders/forwards
TEAM_DEFENCE_PRICE_PLAYERS = 5  # and five most expensive goalkeepers/defenders


def player_prices(players: pd.DataFrame) -> pd.Series | None:
    """Each player's start-of-season price (current price if that's missing),
    indexed by p_id, or None if the inputs have no prices.

    The start-of-season price is fixed before a ball is kicked, so using it
    leaks nothing from the games being predicted (the backtest stays fair).
    """
    columns = [c for c in ("p_start_price", "p_price") if c in players.columns]
    if not columns:
        return None
    prices = players.set_index("p_id")[columns].apply(pd.to_numeric, errors="coerce").bfill(axis=1).iloc[:, 0]
    return prices.where(prices > 0)


def relative_price(players: pd.DataFrame, cfg: ModelConfig) -> pd.Series:
    """(price / the position's average price) ** price_prior_power, by p_id:
    the multiplier on the position average a player's rates are shrunk
    towards. 1.0 when there are no prices or the prior is off."""
    ones = pd.Series(1.0, index=players["p_id"].values)
    prices = player_prices(players)
    if prices is None or cfg.price_prior_power == 0:
        return ones
    position = players.set_index("p_id")["p_position"]
    relative = prices / prices.groupby(position).transform("mean")
    return (relative**cfg.price_prior_power).reindex(ones.index).fillna(1.0)


def team_price_priors(players: pd.DataFrame, team_ids, cfg: ModelConfig) -> tuple[pd.Series, pd.Series] | None:
    """What each team's attack and defence ratings are shrunk towards,
    from what its best-priced players cost relative to the league: the mean
    price of its six dearest midfielders/forwards (attack) and five dearest
    goalkeepers/defenders (defence, inverted: an expensive defence concedes
    less). None when there are no prices or the prior is off."""
    prices = player_prices(players)
    if prices is None or cfg.team_price_prior_power == 0:
        return None
    frame = players[["p_id", "p_team", "p_position"]].assign(price=players["p_id"].map(prices)).dropna()

    def top_mean(positions, n):
        chosen = frame[frame["p_position"].isin(positions)].sort_values("price", ascending=False)
        return chosen.groupby("p_team").head(n).groupby("p_team")["price"].mean()

    attack = top_mean([3, 4], TEAM_ATTACK_PRICE_PLAYERS)
    defence = top_mean([1, 2], TEAM_DEFENCE_PRICE_PLAYERS)
    power = cfg.team_price_prior_power
    team_ids = sorted({int(t) for t in team_ids})
    return (
        ((attack / attack.mean()) ** power).reindex(team_ids).fillna(1.0),
        ((defence / defence.mean()) ** -power).reindex(team_ids).fillna(1.0),
    )


# ---------------------------------------------------------------------------
# 1. Team ratings
# ---------------------------------------------------------------------------


def team_matches(inputs: ModelInputs, as_of_gw: int) -> pd.DataFrame:
    """One row per team per past match with its xG for and against.

    Player stats are per gameweek, so a team's gameweek xG is split evenly
    across its matches in a double gameweek.
    """
    history = _history(inputs, as_of_gw)
    played = history[history["pg_minutes"] > 0].merge(
        inputs.players[["p_id", "p_team"]], left_on="pg_id", right_on="p_id"
    )
    team_gw_xg = played.groupby(["p_team", "pg_gameweek"])["pg_xg"].sum().rename("gw_xg").reset_index()
    team_gw_xg.columns = ["team_id", "gw", "gw_xg"]

    sides = _team_fixtures(inputs.fixtures)
    sides = sides[sides["gw"] < as_of_gw]
    sides["n_matches"] = sides.groupby(["team_id", "gw"])["f_id"].transform("count")
    sides = sides.merge(team_gw_xg, on=["team_id", "gw"], how="inner")
    sides["xg_for"] = sides["gw_xg"] / sides["n_matches"]

    against = sides[["team_id", "gw", "xg_for"]].groupby(["team_id", "gw"], as_index=False)["xg_for"].first()
    against.columns = ["opponent_id", "gw", "xg_against"]
    return sides.merge(against, on=["opponent_id", "gw"], how="inner")[
        ["f_id", "gw", "team_id", "opponent_id", "is_home", "xg_for", "xg_against"]
    ]


def fit_team_ratings(
    matches: pd.DataFrame,
    team_ids,
    as_of_gw: int,
    cfg: ModelConfig,
    iterations: int = 50,
    priors: tuple[pd.Series, pd.Series] | None = None,
) -> tuple[pd.DataFrame, float]:
    """Attack/defence multipliers (1.0 = league average) and the league's
    average xG per team per match.

    Solves ``xg_for ~ league_avg x attack[team] x defence[opponent] x venue``
    by iterative proportional fitting, so a side that has faced strong
    defences isn't marked down for it. Each update adds
    ``team_prior_matches`` of prior performance, which pulls ratings built
    on few matches towards 1.0, or towards ``priors`` (attack, defence by
    team; see team_price_priors) when given.
    """
    team_ids = sorted({int(t) for t in team_ids})
    attack = pd.Series(1.0, index=team_ids)
    defence = pd.Series(1.0, index=team_ids)
    if matches.empty:
        return pd.DataFrame({"team_id": team_ids, "attack": 1.0, "defence": 1.0}), 1.35

    m = matches.copy()
    m["w"] = cfg.team_decay ** (as_of_gw - 1 - m["gw"])
    league_avg = float((m["xg_for"] * m["w"]).sum() / m["w"].sum())
    m["venue_for"] = _venue(m["is_home"], cfg.home_advantage)
    m["venue_against"] = 1.0 / m["venue_for"]
    prior = cfg.team_prior_matches * league_avg
    prior_attack, prior_defence = priors or (1.0, 1.0)

    def per_team(values: pd.Series) -> pd.Series:
        return values.groupby(m["team_id"]).sum().reindex(team_ids, fill_value=0.0)

    for _ in range(iterations):
        base_for = league_avg * m["opponent_id"].map(defence) * m["venue_for"]
        attack = (per_team(m["w"] * m["xg_for"]) + prior * prior_attack) / (per_team(m["w"] * base_for) + prior)
        attack /= attack.mean()

        base_against = league_avg * m["opponent_id"].map(attack) * m["venue_against"]
        defence = (per_team(m["w"] * m["xg_against"]) + prior * prior_defence) / (
            per_team(m["w"] * base_against) + prior
        )
        defence /= defence.mean()

    ratings = pd.DataFrame({"team_id": team_ids, "attack": attack.values, "defence": defence.values})
    return ratings, league_avg


DEFCON_POSITIONS = (2, 3)  # the positions whose actions measure an opponent


def team_defcon_matches(inputs: ModelInputs, as_of_gw: int) -> pd.DataFrame:
    """One row per team per past match: defensive actions made by its
    defenders and midfielders (split evenly across a double gameweek)."""
    history = _history(inputs, as_of_gw)
    played = history[history["pg_minutes"] > 0].merge(
        inputs.players[["p_id", "p_team", "p_position"]], left_on="pg_id", right_on="p_id"
    )
    played = played[played["p_position"].isin(DEFCON_POSITIONS)]
    made = played.groupby(["p_team", "pg_gameweek"])["pg_defcons"].sum().reset_index()
    made.columns = ["team_id", "gw", "gw_defcons"]

    sides = _team_fixtures(inputs.fixtures)
    sides = sides[sides["gw"] < as_of_gw]
    sides["n_matches"] = sides.groupby(["team_id", "gw"])["f_id"].transform("count")
    sides = sides.merge(made, on=["team_id", "gw"], how="inner")
    sides["defcons"] = sides["gw_defcons"] / sides["n_matches"]
    return sides[["f_id", "gw", "team_id", "opponent_id", "defcons"]]


def fit_defcon_allowed(
    matches: pd.DataFrame, team_ids, as_of_gw: int, cfg: ModelConfig, iterations: int = 50
) -> pd.Series:
    """How many defensive actions each team's opponents make against it
    (1.0 = average, 1.1 = 10% more), indexed by team.

    The same method as the team ratings: ``defcons ~ league average x
    makes[team] x allowed[opponent]`` by iterative proportional fitting, so a
    team isn't credited with "giving away" actions just because it played
    sides that make lots of them, shrunk by ``defcon_prior_matches``. Home and
    away sides make about the same number, so there is no venue term.
    """
    team_ids = sorted({int(t) for t in team_ids})
    allowed = pd.Series(1.0, index=team_ids)
    if matches.empty or not cfg.use_defcon_opponent:
        return allowed
    makes = pd.Series(1.0, index=team_ids)
    m = matches
    w = cfg.team_decay ** (as_of_gw - 1 - m["gw"])
    league_avg = float((m["defcons"] * w).sum() / w.sum())
    if league_avg <= 0:
        return allowed
    prior = cfg.defcon_prior_matches * league_avg
    observed_made = (w * m["defcons"]).groupby(m["team_id"]).sum()
    observed_allowed = (w * m["defcons"]).groupby(m["opponent_id"]).sum()
    for _ in range(iterations):
        base = w * league_avg * m["opponent_id"].map(allowed)
        makes = (observed_made.add(prior) / base.groupby(m["team_id"]).sum().add(prior)).reindex(team_ids).fillna(1.0)
        makes /= makes.mean()
        base = w * league_avg * m["team_id"].map(makes)
        allowed = (
            (observed_allowed.add(prior) / base.groupby(m["opponent_id"]).sum().add(prior))
            .reindex(team_ids)
            .fillna(1.0)
        )
        allowed /= allowed.mean()
    return allowed


# ---------------------------------------------------------------------------
# Previous seasons as a prior
# ---------------------------------------------------------------------------

HISTORY_STATS = ("xg", "xa", "base_bps", "defcons", "saves", "yellow")
MOVER_WINDOW_DAYS = 120  # joined his club this close to (or after) the first deadline


def _season_start(gameweeks: pd.DataFrame) -> pd.Timestamp | None:
    deadlines = pd.to_datetime(gameweeks["gw_deadline_time"], utc=True, errors="coerce").dropna()
    return deadlines.min() if not deadlines.empty else None


def history_rates(inputs: ModelInputs, cfg: ModelConfig) -> pd.DataFrame:
    """Per player, per-90 rates from his previous Premier League seasons and
    the (season-weighted) 90s behind each, as ``<stat>_hist`` and
    ``<stat>_hist_90s``. Empty when there's no history.

    * xG is open play: penalty_xg is removed for every penalty taken.
    * Base BPS is BPS minus the parts from goals, assists, clean sheets,
      goals conceded, saves and missed penalties, as for this season.
    * Defensive actions are counted the way his *current* position counts
      them (defenders: clearances/blocks/interceptions + tackles;
      midfielders/forwards: + recoveries), from the components where the
      season has them, otherwise FPL's defensive_contribution total.
    """
    columns = ["p_id"] + [c for s in HISTORY_STATS for c in (f"{s}_hist", f"{s}_hist_90s")]
    history = inputs.history
    if not cfg.use_history or history is None or history.empty:
        return pd.DataFrame(columns=columns)

    weights = dict(enumerate(cfg.history_season_weights, start=1))
    h = history[history["ps_seasons_ago"].isin(list(weights))].copy()
    h = h.merge(inputs.players[["p_id", "p_position", "p_team"]], on="p_id")
    if h.empty:
        return pd.DataFrame(columns=columns)
    num = lambda c: pd.to_numeric(h[c], errors="coerce") if c in h else pd.Series(np.nan, index=h.index)  # noqa: E731

    h["w"] = h["ps_seasons_ago"].map(weights)
    start = _season_start(inputs.gameweeks)
    if start is not None and "ps_team_join_date" in h:
        joined = pd.to_datetime(h["ps_team_join_date"], utc=True, errors="coerce")
        mover = joined >= start - pd.Timedelta(days=MOVER_WINDOW_DAYS)
        h["w"] *= np.where(mover.fillna(False), cfg.history_mover_weight, 1.0)
    h["nineties"] = num("ps_minutes").fillna(0) / 90.0

    pens = num("ps_penalties_taken").fillna(0)
    stat_totals = {
        "xg": (num("ps_xg") - cfg.penalty_xg * pens).clip(lower=0),
        "xa": num("ps_xa"),
        "base_bps": num("ps_bps")
        - event_bps(
            pd.DataFrame(
                {
                    "p_position": h["p_position"],
                    "pg_goals": num("ps_goals").fillna(0),
                    "pg_assists": num("ps_assists").fillna(0),
                    "pg_clean_sheets": num("ps_clean_sheets").fillna(0),
                    "pg_goals_conceded": num("ps_goals_conceded").fillna(0),
                    "pg_saves": num("ps_saves").fillna(0),
                    "pg_pens_missed": num("ps_penalties_missed").fillna(0),
                }
            )
        ),
        "saves": num("ps_saves"),
        "yellow": num("ps_yellow_cards"),
    }
    cbit = num("ps_cbi") + num("ps_tackles")
    cbirt = cbit + num("ps_recoveries")
    components = np.where(h["p_position"].isin([3, 4]), cbirt, cbit)
    stat_totals["defcons"] = pd.Series(components, index=h.index).fillna(num("ps_defensive_contribution"))

    out = pd.DataFrame(index=pd.Index(sorted(h["p_id"].unique()), name="p_id"))
    for stat, totals in stat_totals.items():
        has = totals.notna() & (h["nineties"] > 0)
        w90 = (h["w"] * h["nineties"]).where(has, 0.0)
        sums = pd.DataFrame({"value": (h["w"] * totals).where(has, 0.0), "w90": w90, "p_id": h["p_id"]})
        sums = sums.groupby("p_id")[["value", "w90"]].sum()
        out[f"{stat}_hist"] = sums["value"] / sums["w90"].replace(0, np.nan)
        out[f"{stat}_hist_90s"] = sums["w90"]
    return out.reset_index()[columns]


# ---------------------------------------------------------------------------
# 2. Player per-90 rates
# ---------------------------------------------------------------------------


def player_rates(inputs: ModelInputs, ratings: pd.DataFrame, as_of_gw: int, cfg: ModelConfig) -> pd.DataFrame:
    """Recency-weighted, opponent-adjusted, shrunk per-90 rates per player.

    xG and xA are divided by how leaky that gameweek's opponents were (so
    output against weak defences counts for less); saves by how dangerous the
    opponents' attack was. Each rate is then blended with the position
    average using ``rate_prior_90s[stat]`` 90s' worth of average play; for
    xG, xA and base BPS that average is scaled by his relative price (see
    relative_price), so an expensive player with few minutes is pulled
    towards what his price says rather than towards a squad player's output.
    """
    history = _history(inputs, as_of_gw)
    rows = history[history["pg_minutes"] > 0].merge(
        inputs.players[["p_id", "p_team", "p_position"]], left_on="pg_id", right_on="p_id"
    )

    # Opponent context per team-gameweek (averaged over a double gameweek).
    sides = _team_fixtures(inputs.fixtures)
    sides = sides[sides["gw"] < as_of_gw].merge(ratings, left_on="opponent_id", right_on="team_id", suffixes=("", "_o"))
    venue = _venue(sides["is_home"], cfg.home_advantage)
    sides["attack_context"] = sides["defence"] * venue
    sides["defence_context"] = sides["attack"] / venue
    sides["defcon_context"] = sides.get("defcon_allowed", 1.0)
    contexts = ["attack_context", "defence_context", "defcon_context"]
    context = sides.groupby(["team_id", "gw"], as_index=False)[contexts].mean()
    rows = rows.merge(context, left_on=["p_team", "pg_gameweek"], right_on=["team_id", "gw"], how="left")
    rows[contexts] = rows[contexts].fillna(1.0)

    rows["adj_xg"] = rows["pg_xg"] / rows["attack_context"]
    rows["adj_xa"] = rows["pg_xa"] / rows["attack_context"]
    rows["adj_saves"] = rows["pg_saves"] / rows["defence_context"]
    rows["adj_defcons"] = rows["pg_defcons"] / rows["defcon_context"]
    rows["base_bps"] = rows["pg_bps"] - event_bps(rows)
    rows["nineties"] = rows["pg_minutes"] / 90.0
    rows["w"] = cfg.form_decay ** (as_of_gw - 1 - rows["pg_gameweek"])

    value_columns = {
        "xg": "adj_xg",
        "xa": "adj_xa",
        "defcons": "adj_defcons",
        "saves": "adj_saves",
        "base_bps": "base_bps",
        "yellow": "pg_yellow_cards",
    }

    # Position averages (unweighted, per 90) are the shrinkage targets.
    by_position = rows.groupby("p_position")
    position_means = {
        stat: by_position[col].sum() / by_position["nineties"].sum().replace(0, np.nan)
        for stat, col in value_columns.items()
    }

    weighted = rows.assign(**{f"w_{s}": rows[c] * rows["w"] for s, c in value_columns.items()})
    weighted["w_nineties"] = rows["nineties"] * rows["w"]
    sums = weighted.groupby("pg_id")[[f"w_{s}" for s in value_columns] + ["w_nineties"]].sum()

    out = inputs.players[["p_id", "p_position"]].set_index("p_id")
    out = out.join(sums, how="left").fillna({c: 0.0 for c in sums.columns})
    price_factor = relative_price(inputs.players, cfg).reindex(out.index).fillna(1.0)
    history = history_rates(inputs, cfg).set_index("p_id").reindex(out.index).astype(float)
    fade = cfg.history_fade ** max(as_of_gw - 1, 0)
    for stat in value_columns:
        k = cfg.rate_prior_90s[stat]
        prior_mean = out["p_position"].map(position_means[stat]).fillna(0.0)
        if stat in PRICE_PRIOR_STATS:
            prior_mean = prior_mean * price_factor
        if stat in HISTORY_STATS and f"{stat}_hist" in history:
            # Previous seasons replace the price/position prior as far as
            # enough past minutes back them, and add weight to it.
            past_90s = history[f"{stat}_hist_90s"].fillna(0.0)
            trust = (past_90s / (past_90s + cfg.history_confidence_90s)).where(history[f"{stat}_hist"].notna(), 0.0)
            prior_mean = trust * history[f"{stat}_hist"].fillna(0.0) + (1 - trust) * prior_mean
            k = k + cfg.history_prior_90s * trust * fade
        out[f"{stat}_p90"] = (out.get(f"w_{stat}", 0.0) + k * prior_mean) / (out["w_nineties"] + k)
    out = out.rename(columns={"w_nineties": "weighted_90s"})
    return out[[f"{s}_p90" for s in value_columns] + ["weighted_90s"]].reset_index()


def event_bps(rows: pd.DataFrame) -> pd.Series:
    """The BPS a player-gameweek earned from goals, assists, clean sheets,
    goals conceded, saves and missed penalties -- the parts the model
    projects fixture by fixture. The rest of his BPS is his "base"."""
    pos = rows["p_position"].astype(int)
    back = pos.isin([1, 2])
    return (
        pos.map(BPS_GOAL) * rows["pg_goals"]
        + BPS_ASSIST * rows["pg_assists"]
        + np.where(back, BPS_CLEAN_SHEET * rows["pg_clean_sheets"] + BPS_GOAL_CONCEDED * rows["pg_goals_conceded"], 0)
        + np.where(pos == 1, BPS_SAVE * rows["pg_saves"], 0)
        + BPS_PENALTY_MISS * rows["pg_pens_missed"]
    )


@dataclass(frozen=True)
class BonusModel:
    """BPS -> expected bonus curve, how much a player's base BPS varies from
    match to match around his average, and the bonus points handed out per
    match (3 + 2 + 1, a little more with ties)."""

    bps: np.ndarray
    bonus: np.ndarray
    base_sd: float
    per_match: float = DEFAULT_BONUS_PER_MATCH


def bonus_model(inputs: ModelInputs, as_of_gw: int, cfg: ModelConfig) -> BonusModel:
    """Learned from this season's 60+ minute appearances before ``as_of_gw``
    (single-fixture gameweeks only).

    * Curve: average bonus per 2-BPS bin, forced to be non-decreasing
      (pool-adjacent-violators). Falls back to ``DEFAULT_BONUS_CURVE`` until
      there's enough data.
    * Base BPS spread: the within-player standard deviation of base BPS
      (default 5). It matters because bonus is a threshold: a player who
      averages 20 base BPS sometimes has a 30-BPS day.
    """
    rows = _history(inputs, as_of_gw)
    rows = rows[rows["pg_minutes"].between(60, 90)].merge(
        inputs.players[["p_id", "p_position"]], left_on="pg_id", right_on="p_id"
    )
    if len(rows) < cfg.bonus_curve_min_rows:
        xs, ys = zip(*DEFAULT_BONUS_CURVE, strict=True)
        return BonusModel(np.array(xs, dtype=float), np.array(ys, dtype=float), cfg.default_base_bps_sd)

    matches = len(team_matches(inputs, as_of_gw)) / 2
    history = _history(inputs, as_of_gw)
    per_match = float(history["pg_bonus"].sum() / matches) if matches >= 20 else DEFAULT_BONUS_PER_MATCH

    base = rows["pg_bps"] - event_bps(rows)
    counts = base.groupby(rows["pg_id"]).transform("size")
    deviations = (base - base.groupby(rows["pg_id"]).transform("mean"))[counts >= 3]
    n = counts[counts >= 3].mean() if len(deviations) else 0
    base_sd = float(deviations.std() * np.sqrt(n / (n - 1))) if len(deviations) > 30 else cfg.default_base_bps_sd

    bins = rows.groupby((rows["pg_bps"] // 2) * 2 + 1)["pg_bonus"].agg(["mean", "size"]).sort_index()
    means, weights = bins["mean"].tolist(), bins["size"].astype(float).tolist()
    blocks: list[list[float]] = []  # [mean, weight, n_bins]
    for mean, weight in zip(means, weights, strict=True):
        blocks.append([mean, weight, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            m2, w2, n2 = blocks.pop()
            m1, w1, n1 = blocks.pop()
            blocks.append([(m1 * w1 + m2 * w2) / (w1 + w2), w1 + w2, n1 + n2])
    fitted = np.repeat([b[0] for b in blocks], [b[2] for b in blocks])
    return BonusModel(bins.index.to_numpy(dtype=float), np.clip(fitted, 0.0, 3.0), base_sd, per_match)


def expected_bonus(f: pd.DataFrame, bonus: BonusModel, cfg: ModelConfig) -> np.ndarray:
    """Expected bonus points per player-fixture from projected BPS.

    Conditional on starting, a player's match BPS is his base BPS rate x his
    usual minutes, plus the BPS from whatever he does in *this* fixture:
    goals (open play and penalties), assists, a clean sheet or goals
    conceded, saves. Because bonus only goes to the top three, what matters
    is the chance of a big BPS score, not the average -- so the model runs
    through the likely scenarios (0-3 goals, 0-2 assists, clean sheet or
    not) and a spread of base-BPS days around his average, converts each
    scenario's BPS to expected bonus with the learned curve, and weights by
    probability. Substitutes rarely get bonus, so only starts count.
    """
    xs, ys = bonus.bps, bonus.bonus
    # Normal spread of base BPS, integrated with Gauss-Hermite quadrature.
    nodes, weights = np.polynomial.hermite_e.hermegauss(7)
    weights = weights / weights.sum()
    pos = f["p_position"].astype(int).to_numpy()
    back = np.isin(pos, [1, 2])
    start_nineties = (f["minutes_if_start"] / 90.0).to_numpy()
    on_pitch = np.clip(f["xmins"].to_numpy() / 90.0, 0.05, 1.0)

    # Everything below is conditional on starting.
    goals_mu = (f["xg_p90"] * start_nineties * f["attack_context"]).to_numpy()
    pens_mu = f["xpens"].to_numpy() / on_pitch
    goals_mu = goals_mu + cfg.penalty_conversion * pens_mu
    assists_mu = (f["xa_p90"] * start_nineties * f["attack_context"]).to_numpy()
    conceded_mu = f["opp_xg"].to_numpy() * start_nineties
    p_zero = goals_zero_prob(conceded_mu, cfg.goals_dispersion)
    p_cs = np.where(back, f["p60_if_start"].to_numpy() * p_zero, 0.0)
    conceded_if_not_cs = np.where(back, conceded_mu / np.clip(1.0 - p_zero, 1e-6, None), 0.0)

    base = (
        f["base_bps_p90"].to_numpy() * start_nineties
        + np.where(pos == 1, BPS_SAVE * (f["saves_p90"] * start_nineties * f["defence_context"]).to_numpy(), 0.0)
        + BPS_PENALTY_MISS * (1 - cfg.penalty_conversion) * pens_mu
    )
    goal_bps = np.vectorize(BPS_GOAL.get)(pos).astype(float)

    def poisson(mu, k, last):
        mu = np.clip(mu, 0.0, None)
        pmf = np.exp(-mu) * mu**k / np.prod(range(1, k + 1))
        if last:  # the final bucket takes the tail
            pmf = 1.0 - sum(np.exp(-mu) * mu**i / np.prod(range(1, i + 1)) for i in range(k))
        return pmf

    total = np.zeros(len(f))
    for goals in range(4):
        p_goals = poisson(goals_mu, goals, goals == 3)
        for assists in range(3):
            p_assists = poisson(assists_mu, assists, assists == 2)
            for cs in (0, 1):
                p_cs_state = np.where(cs == 1, p_cs, 1.0 - p_cs)
                defence = np.where(
                    back,
                    np.where(cs == 1, BPS_CLEAN_SHEET, BPS_GOAL_CONCEDED * conceded_if_not_cs),
                    0.0,
                )
                bps = base + goals * goal_bps + assists * BPS_ASSIST + defence
                p_state = p_goals * p_assists * p_cs_state
                for node, weight in zip(nodes, weights, strict=True):
                    total += p_state * weight * np.interp(bps + node * bonus.base_sd, xs, ys)
    return f["p_start"].to_numpy() * total


# ---------------------------------------------------------------------------
# 3. Minutes and availability
# ---------------------------------------------------------------------------


def _counting_from(history: pd.DataFrame) -> pd.Series:
    """The gameweek each player's selection record starts from: his first
    row in the data, or -- if he was added after the season's first
    gameweek -- his debut."""
    if history.empty:
        return pd.Series(dtype=float)
    season_start = history["pg_gameweek"].min()
    first_row = history.groupby("pg_id")["pg_gameweek"].min()
    debut = history[history["pg_minutes"] > 0].groupby("pg_id")["pg_gameweek"].min()
    joined_late = first_row > season_start
    return first_row.where(~joined_late, debut.reindex(first_row.index))


def minutes_model(inputs: ModelInputs, as_of_gw: int, cfg: ModelConfig) -> pd.DataFrame:
    """Per player: P(start), P(sub appearance), minutes when starting / from
    the bench, and P(60+ minutes | start), from his team's recent matches.

    Only gameweeks since he arrived count. FPL's live data only lists
    players who were in the game at the time, so a player with no row for a
    gameweek hadn't joined yet. And a player added mid-season (a new
    signing) is judged from his debut: gameweeks before it, while he was
    registering or getting fit, say nothing about whether he's first choice.
    For players in the game from the start, a gameweek without minutes is an
    unused squad place.
    """
    sides = _team_fixtures(inputs.fixtures)
    team_gws = sides[sides["gw"] < as_of_gw].groupby(["team_id", "gw"]).size().rename("n_matches").reset_index()
    history = _history(inputs, as_of_gw)[["pg_id", "pg_gameweek", "pg_minutes", "pg_starts"]]

    grid = inputs.players[["p_id", "p_team"]].merge(team_gws, left_on="p_team", right_on="team_id")
    grid = grid.merge(history, left_on=["p_id", "gw"], right_on=["pg_id", "pg_gameweek"], how="left")
    grid = grid[grid["gw"] >= grid["p_id"].map(_counting_from(history)).fillna(np.inf)]
    grid[["pg_minutes", "pg_starts"]] = grid[["pg_minutes", "pg_starts"]].fillna(0.0)
    grid["w"] = cfg.minutes_decay ** (as_of_gw - 1 - grid["gw"])

    starts = grid["pg_starts"].clip(upper=grid["n_matches"])
    sub_only = ((grid["pg_minutes"] > 0) & (starts == 0)).astype(float)
    start_minutes = np.where(starts > 0, grid["pg_minutes"], 0.0)
    minutes_per_start = np.where(starts > 0, grid["pg_minutes"] / starts.replace(0, np.nan), 0.0)
    grid = grid.assign(
        w_matches=grid["w"] * grid["n_matches"],
        w_starts=grid["w"] * starts,
        w_subs=grid["w"] * sub_only,
        w_start_minutes=grid["w"] * start_minutes,
        w_sub_minutes=grid["w"] * np.where(sub_only > 0, grid["pg_minutes"], 0.0),
        w_starts_60=grid["w"] * starts * (minutes_per_start >= 60),
    )
    s = grid.groupby("p_id")[
        ["w_matches", "w_starts", "w_subs", "w_start_minutes", "w_sub_minutes", "w_starts_60"]
    ].sum()

    out = pd.DataFrame(index=inputs.players["p_id"])
    out = out.join(s, how="left").fillna(0.0)
    matches = out["w_matches"].replace(0, np.nan)
    out["p_start"] = (out["w_starts"] / matches).fillna(0.0).clip(upper=cfg.start_prob_cap)
    out["p_sub"] = (out["w_subs"] / matches).fillna(0.0).clip(upper=1.0 - out["p_start"])
    out["minutes_if_start"] = (out["w_start_minutes"] / out["w_starts"].replace(0, np.nan)).fillna(
        cfg.default_minutes_if_start
    )
    out["minutes_if_sub"] = (out["w_sub_minutes"] / out["w_subs"].replace(0, np.nan)).fillna(cfg.default_minutes_if_sub)
    out["p60_if_start"] = (out["w_starts_60"] / out["w_starts"].replace(0, np.nan)).fillna(cfg.default_p60_given_start)
    return out[["p_start", "p_sub", "minutes_if_start", "minutes_if_sub", "p60_if_start"]].reset_index()


_RETURN_DATE = re.compile(r"(?:expected back|until)\s+(\d{1,2})\s+([A-Za-z]{3})", re.IGNORECASE)


def parse_return_date(news: str | None, reference: date) -> date | None:
    """The return date in FPL news such as "Hamstring injury - Expected back
    18 Oct" or "Suspended until 04 Nov", in the year that puts it after
    (or shortly before) ``reference``."""
    if not isinstance(news, str):
        return None
    match = _RETURN_DATE.search(news)
    if not match:
        return None
    try:
        parsed = datetime.strptime(f"{match.group(1)} {match.group(2).title()} {reference.year}", "%d %b %Y").date()
    except ValueError:
        return None
    if parsed < reference - timedelta(days=60):
        parsed = parsed.replace(year=parsed.year + 1)
    return parsed


def availability(players: pd.DataFrame, horizon: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    """Chance each player is available in each horizon gameweek.

    ``horizon`` has gw, gw_index (0 = next) and deadline. FPL statuses: a =
    available, d = doubtful, i = injured, s = suspended, u = unavailable (left
    the club), n = not eligible (e.g. on loan to the opponent).

    * Next gameweek: FPL's own chance-of-playing percentage.
    * Later gameweeks: unavailable until a return date given in the news;
      without one, the chance recovers by ``recovery_per_gameweek`` of the
      remaining gap each week.
    """
    grid = players[["p_id", "p_status", "p_chance_of_playing", "p_news"]].merge(horizon, how="cross")
    if not cfg.use_availability or grid.empty:
        return grid.assign(availability=1.0)[["p_id", "gw", "availability"]]

    status = grid["p_status"].fillna("a")
    chance = (grid["p_chance_of_playing"] / 100.0).where(grid["p_chance_of_playing"].notna())
    chance = chance.fillna(cfg.flagged_default_chance)

    reference = pd.to_datetime(horizon["deadline"], utc=True).min().date()
    returns = players.set_index("p_id")["p_news"].map(lambda n: parse_return_date(n, reference))
    return_date = pd.to_datetime(grid["p_id"].map(returns), utc=True)
    deadline = pd.to_datetime(grid["deadline"], utc=True)

    recovered = 1.0 - (1.0 - chance) * cfg.recovery_per_gameweek ** grid["gw_index"]
    flagged = np.where(
        grid["gw_index"] == 0,
        chance,
        np.where(return_date.notna(), np.where(deadline < return_date, 0.0, 1.0), recovered),
    )
    value = np.select([status.isin(["u", "n"]), status == "a"], [0.0, 1.0], default=flagged)
    return grid.assign(availability=value)[["p_id", "gw", "availability"]]


# ---------------------------------------------------------------------------
# 4. Fixture-level expected points
# ---------------------------------------------------------------------------

POINT_COMPONENTS = [
    "pts_appearance",
    "pts_goals",
    "pts_assists",
    "pts_penalties",
    "pts_clean_sheet",
    "pts_goals_conceded",
    "pts_saves",
    "pts_defcon",
    "pts_bonus",
    "pts_cards",
]


def goals_per_xg(inputs: ModelInputs, as_of_gw: int, cfg: ModelConfig) -> float:
    """Goals scored per xG this season (before ``as_of_gw``), shrunk towards
    1.0 by ``goals_per_xg_prior`` xG's worth of 1:1. Over a whole season
    goals and xG match closely, but a few weeks can run hot or cold for
    everyone (e.g. 1.41 goals per team per match from 1.53 xG)."""
    history = _history(inputs, as_of_gw)
    goals, xg = float(history["pg_goals"].sum()), float(history["pg_xg"].sum())
    prior = cfg.goals_per_xg_prior
    return (goals + prior) / (xg + prior)


def open_play_inputs(inputs: ModelInputs, cfg: ModelConfig) -> ModelInputs:
    """``inputs`` with penalty xG removed from every player-gameweek's xG, so
    everything learned from xG (team ratings, player rates) is open play."""
    penalties = inputs.penalties
    if penalties is None or penalties.empty:
        return inputs
    taken = penalties.groupby(["p_id", "gw_id"])["penalties_taken"].sum()
    stats = inputs.stats.copy()
    key = pd.MultiIndex.from_arrays([stats["pg_id"], stats["pg_gameweek"]])
    penalty_xg = cfg.penalty_xg * pd.Series(taken.reindex(key).fillna(0).to_numpy(), index=stats.index)
    stats["pg_xg"] = (stats["pg_xg"] - penalty_xg).clip(lower=0.0)
    return replace(inputs, stats=stats)


def league_penalty_rate(inputs: ModelInputs, as_of_gw: int, cfg: ModelConfig) -> float:
    """Penalties per team per match before ``as_of_gw``, shrunk towards the
    long-run rate by ``penalty_prior_matches`` matches of it."""
    penalties = inputs.penalties
    taken = 0.0 if penalties is None else float(penalties.loc[penalties["gw_id"] < as_of_gw, "penalties_taken"].sum())
    team_matches_played = len(team_matches(inputs, as_of_gw))
    prior = cfg.penalty_prior_matches
    return (taken + cfg.penalty_rate_prior * prior) / (team_matches_played + prior)


def penalty_shares(f: pd.DataFrame) -> pd.Series:
    """Each player's share of his team's penalties in a fixture.

    Takers are tried in FPL's penalty order: the first-choice taker takes it
    if he's on the pitch (expected minutes / 90), otherwise it falls to the
    next, and so on. Players without an order get nothing.
    """
    shares = pd.Series(0.0, index=f.index)
    if "p_penalties_order" not in f.columns:
        return shares
    takers = f[f["p_penalties_order"].notna()].sort_values(["team_id", "f_id", "p_penalties_order"])
    if takers.empty:
        return shares
    on_pitch = (takers["xmins"] / 90.0).clip(0.0, 1.0)
    # Chance that nobody earlier in the order is on the pitch.
    missing_before = (
        (1.0 - on_pitch)
        .groupby([takers["team_id"], takers["f_id"]])
        .transform(lambda s: s.shift(fill_value=1.0).cumprod())
    )
    shares.loc[takers.index] = on_pitch * missing_before
    return shares


def project(inputs: ModelInputs, as_of_gw: int, cfg: ModelConfig | None = None) -> Projection:
    """Expected points for every player in every fixture of the
    ``cfg.horizon`` gameweeks from ``as_of_gw``, using only data from
    earlier gameweeks."""
    cfg = cfg or ModelConfig()
    goal_rate = goals_per_xg(inputs, as_of_gw, cfg)  # before penalties come out of xG
    model_penalties = cfg.use_penalties and inputs.penalties is not None
    if model_penalties:
        inputs = open_play_inputs(inputs, cfg)
    players = inputs.players.copy()
    team_ids = (
        set(players["p_team"].dropna()) | set(inputs.fixtures["f_home_team"]) | set(inputs.fixtures["f_away_team"])
    )

    ratings, league_avg = fit_team_ratings(
        team_matches(inputs, as_of_gw), team_ids, as_of_gw, cfg, priors=team_price_priors(players, team_ids, cfg)
    )
    defcon_allowed = fit_defcon_allowed(team_defcon_matches(inputs, as_of_gw), team_ids, as_of_gw, cfg)
    ratings["defcon_allowed"] = ratings["team_id"].map(defcon_allowed).fillna(1.0)
    rates = player_rates(inputs, ratings, as_of_gw, cfg)
    bonus = bonus_model(inputs, as_of_gw, cfg)
    minutes = minutes_model(inputs, as_of_gw, cfg)

    gws = inputs.gameweeks.sort_values("gw_id")
    horizon = gws[gws["gw_id"] >= as_of_gw].head(cfg.horizon)
    horizon = pd.DataFrame(
        {
            "gw": horizon["gw_id"].astype(int).values,
            "gw_index": range(len(horizon)),
            "deadline": horizon["gw_deadline_time"].values,
        }
    )
    avail = availability(players, horizon, cfg)

    sides = _team_fixtures(inputs.fixtures)
    sides = sides[sides["gw"].isin(horizon["gw"])]
    team_side = ratings.drop(columns="defcon_allowed").rename(
        columns={"attack": "team_attack", "defence": "team_defence"}
    )
    opp_side = ratings.rename(
        columns={
            "team_id": "opponent_id",
            "attack": "opp_attack",
            "defence": "opp_defence",
            "defcon_allowed": "defcon_context",  # >1 = more defensive actions against this opponent
        }
    )
    sides = sides.merge(team_side, on="team_id").merge(opp_side, on="opponent_id")
    venue = _venue(sides["is_home"], cfg.home_advantage)
    sides["attack_context"] = sides["opp_defence"] * venue  # >1 = easier to score
    sides["defence_context"] = sides["opp_attack"] / venue  # >1 = more dangerous opponent
    sides["team_xg"] = league_avg * sides["team_attack"] * sides["attack_context"]
    sides["opp_xg"] = league_avg * sides["team_defence"] * sides["defence_context"]
    if model_penalties:
        # Penalties won scale with attacking threat, like xG. Their xG goes
        # back into each side's expected goals for clean sheets/conceded.
        pen_rate = league_penalty_rate(inputs, as_of_gw, cfg)
        sides["team_pens"] = pen_rate * sides["team_attack"] * sides["attack_context"]
        sides["opp_pens"] = pen_rate * sides["team_defence"] * sides["defence_context"]
        sides["team_xg"] += cfg.penalty_xg * sides["team_pens"]
        sides["opp_xg"] += cfg.penalty_xg * sides["opp_pens"]
    else:
        sides["team_pens"] = sides["opp_pens"] = 0.0
    sides["team_xg"] *= goal_rate
    sides["opp_xg"] *= goal_rate

    player_columns = ["p_id", "p_team", "p_position"]
    if "p_penalties_order" in players.columns:
        player_columns.append("p_penalties_order")
    f = (
        players[player_columns]
        .merge(sides, left_on="p_team", right_on="team_id")
        .merge(rates, on="p_id", how="left")
        .merge(minutes, on="p_id", how="left")
        .merge(avail, on=["p_id", "gw"], how="left")
    )
    f["availability"] = f["availability"].fillna(1.0)
    f["xg_p90"] = f["xg_p90"] * goal_rate  # expected goals, not xG
    pos = f["p_position"].astype(int)

    p_start = f["p_start"] * f["availability"]
    p_sub = f["p_sub"] * f["availability"]
    f["p_start"], f["p_sub"] = p_start, p_sub
    f["xmins"] = p_start * f["minutes_if_start"] + p_sub * f["minutes_if_sub"]
    f["p_appear"] = p_start + p_sub
    f["p_60"] = p_start * f["p60_if_start"]
    nineties = f["xmins"] / 90.0
    start_nineties = f["minutes_if_start"] / 90.0

    f["xg"] = f["xg_p90"] * nineties * f["attack_context"]
    f["xa"] = f["xa_p90"] * nineties * f["attack_context"]
    f["cs_prob"] = goals_zero_prob(f["opp_xg"], cfg.goals_dispersion)

    f["xpens"] = f["team_pens"] * penalty_shares(f)
    f["pts_appearance"] = f["p_appear"] + f["p_60"]
    f["pts_goals"] = pos.map(GOAL_POINTS) * f["xg"]
    f["pts_penalties"] = f["xpens"] * (
        cfg.penalty_conversion * pos.map(GOAL_POINTS) + (1 - cfg.penalty_conversion) * PENALTY_MISS_POINTS
    )
    f["pts_assists"] = ASSIST_POINTS * f["xa"]
    f["pts_clean_sheet"] = pos.map(CLEAN_SHEET_POINTS) * f["p_60"] * f["cs_prob"]

    is_back = pos.isin([1, 2]).to_numpy()
    conceded = goals_expected_floor_div(f["opp_xg"] * start_nineties, GOALS_CONCEDED_PER_POINT, cfg.goals_dispersion)
    f["pts_goals_conceded"] = np.where(is_back, -p_start * conceded, 0.0)

    saves = poisson_expected_floor_div(f["saves_p90"] * start_nineties * f["defence_context"], SAVES_PER_POINT)
    f["pts_saves"] = np.where(pos == 1, p_start * saves, 0.0)

    defcon = np.zeros(len(f))
    for position, threshold in DEFCON_THRESHOLD.items():
        mask = (pos == position).to_numpy()
        if mask.any():
            mu = (f["defcons_p90"] * start_nineties * f["defcon_context"])[mask]
            defcon[mask] = DEFCON_POINTS * p_start[mask] * negbin_at_least(mu, threshold, cfg.defcon_dispersion)
    f["pts_defcon"] = defcon

    # Bonus is zero-sum: about 6 points go to each match's top BPS scorers.
    # The scenarios decide who is likely to get them; scale each fixture so
    # its players share the known total.
    f["pts_bonus"] = expected_bonus(f, bonus, cfg)
    fixture_total = f.groupby("f_id")["pts_bonus"].transform("sum")
    f["pts_bonus"] *= (bonus.per_match / fixture_total.where(fixture_total > 0)).fillna(0.0)
    f["pts_cards"] = -f["yellow_p90"] * nineties
    f["xpts"] = f[POINT_COMPONENTS].sum(axis=1)

    fixture_columns = [
        "p_id", "f_id", "gw", "team_id", "opponent_id", "is_home", "availability", "p_start", "p_sub",
        "p_appear", "p_60", "xmins", "xg", "xa", "xpens", "team_xg", "opp_xg", "cs_prob", *POINT_COMPONENTS, "xpts",
    ]  # fmt: skip
    fixtures_out = f[fixture_columns].sort_values(["p_id", "gw", "f_id"]).reset_index(drop=True)

    summary = summarise(players, fixtures_out, rates, horizon, cfg)
    teams_out = ratings.rename(
        columns={"attack": "attack_index", "defence": "defence_index", "defcon_allowed": "defcon_allowed_index"}
    )
    teams_out["league_xg_per_match"] = league_avg
    return Projection(fixtures_out, summary, teams_out, as_of_gw, horizon["gw"].tolist())


# ---------------------------------------------------------------------------
# 5. Player summary and star rating
# ---------------------------------------------------------------------------


def summarise(
    players: pd.DataFrame, fixtures: pd.DataFrame, rates: pd.DataFrame, horizon: pd.DataFrame, cfg: ModelConfig
) -> pd.DataFrame:
    """One row per player: expected points next gameweek and over the
    horizon, the horizon total split by scoring category, expected minutes,
    rates, and a 0-10 star rating (see :func:`star_ratings`).
    """
    n_gws = max(len(horizon), 1)
    next_gw = int(horizon["gw"].iloc[0]) if len(horizon) else None

    totals = fixtures.groupby("p_id")[[*POINT_COMPONENTS, "xpts", "xg", "xa", "xpens", "xmins"]].sum()
    totals = totals.rename(
        columns={
            "xpts": "xpts_horizon",
            "xg": "xg_horizon",
            "xa": "xa_horizon",
            "xpens": "xpens_horizon",
            "xmins": "xmins_horizon",
        }
    )
    next_rows = fixtures[fixtures["gw"] == next_gw].groupby("p_id")
    counts = fixtures.groupby("p_id")["f_id"].nunique().rename("fixtures_in_horizon")

    identity = ["p_id", "p_position"] + (["p_penalties_order"] if "p_penalties_order" in players.columns else [])
    out = players[identity].set_index("p_id")
    out = (
        out.join(totals)
        .join(next_rows["xpts"].sum().rename("xpts_next_gw"))
        .join(next_rows["xmins"].sum().rename("xmins_next_gw"))
        .join(next_rows["availability"].min().rename("availability_next_gw"))
        .join(fixtures.groupby("p_id")["p_start"].max().rename("start_prob"))
        .join(counts)
        .join(rates.set_index("p_id"))
    )
    fill = {
        c: 0.0
        for c in [
            *POINT_COMPONENTS,
            "xpts_horizon",
            "xg_horizon",
            "xa_horizon",
            "xpens_horizon",
            "xmins_horizon",
            "xpts_next_gw",
            "xmins_next_gw",
        ]
    }
    fill["fixtures_in_horizon"] = 0
    out = out.fillna(fill)
    out["xpts_per_gw"] = out["xpts_horizon"] / n_gws
    out["xmins_per_gw"] = out["xmins_horizon"] / n_gws
    out["star"], typical, best = star_ratings(out["xpts_per_gw"], out["xmins_per_gw"], cfg)
    out["star_typical_xpts"], out["star_best_xpts"] = typical, best
    out["position_rank"] = out.groupby("p_position")["xpts_horizon"].rank(method="first", ascending=False).astype(int)
    return out.reset_index()


def star_ratings(xpts_per_gw: pd.Series, xmins_per_gw: pd.Series, cfg: ModelConfig) -> tuple[pd.Series, float, float]:
    """0-10 stars relative to this week's projections.

    A typical regular starter (the median expected points per gameweek among
    players expected to average ``star_regular_minutes``+ minutes) scores 5
    and the best projection scores 10, on a straight line that carries on
    below 5 to 0. Expected points are averages, so they sit in a narrow band
    (roughly 3-6 a gameweek for anyone worth picking); anchoring the scale to
    that band spreads the genuine options out instead of bunching them.

    Returns the stars and the two anchors (typical, best).
    """
    regulars = xpts_per_gw[xmins_per_gw >= cfg.star_regular_minutes]
    if len(regulars) < 5:  # e.g. before any football has been played
        regulars = xpts_per_gw[xpts_per_gw > 0]
    typical = float(regulars.median()) if len(regulars) else 0.0
    best = float(xpts_per_gw.max()) if len(xpts_per_gw) else 0.0
    if best - typical <= 1e-9:
        return pd.Series(np.where(xpts_per_gw > 0, 5.0, 0.0), index=xpts_per_gw.index), typical, best
    stars = (5.0 + 5.0 * (xpts_per_gw - typical) / (best - typical)).clip(0.0, 10.0)
    return stars, typical, best
