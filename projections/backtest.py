"""Backtest: how well does the model predict points it hasn't seen?

For each target gameweek T, the model is fitted on gameweeks before T only
and asked for every player's expected points in T. The prediction is then
compared with the points actually scored, alongside two naive baselines
computed from the same history:

* **form**   -- average points per team match over the last four gameweeks
  (roughly FPL's own "form" figure);
* **season** -- average points per team match so far this season.

Metrics, over players who were in contention (played in T, or in either of
the two gameweeks before it):

* **MAE / RMSE** -- average size of the miss, in points;
* **rank corr.** -- Spearman correlation: does the ordering of players match?
* **top-20 pts** -- average actual points of each method's 20 highest
  predictions: the "if I'd picked by this" test.
* **bias**       -- mean predicted minus mean actual.

FPL availability flags aren't stored historically, so the backtest runs the
model without them -- slightly handicapping it relative to live use.

Usage::

    python projections/backtest.py                 # every gameweek with history
    python projections/backtest.py --from-gw 4     # only targets from GW4
    python projections/backtest.py --compare-priors  # history / price prior settings
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd

from model import ModelConfig, ModelInputs, project

logger = logging.getLogger(__name__)

FORM_WINDOW_GWS = 4
TOP_N = 20
METHODS = ["model", "form", "season"]


def _team_matches_per_gw(inputs: ModelInputs) -> pd.DataFrame:
    fixtures = inputs.fixtures.dropna(subset=["f_gameweek"])
    sides = pd.concat(
        [
            fixtures[["f_gameweek", "f_home_team"]].set_axis(["gw", "team_id"], axis=1),
            fixtures[["f_gameweek", "f_away_team"]].set_axis(["gw", "team_id"], axis=1),
        ]
    )
    return sides.groupby(["team_id", "gw"]).size().rename("n_matches").reset_index()


def baselines(inputs: ModelInputs, target_gw: int) -> pd.DataFrame:
    """Points per team match over the last ``FORM_WINDOW_GWS`` gameweeks and
    over the season, for every player, using gameweeks before ``target_gw``."""
    matches = _team_matches_per_gw(inputs)
    matches = matches[matches["gw"] < target_gw]
    grid = inputs.players[["p_id", "p_team"]].merge(matches, left_on="p_team", right_on="team_id")
    stats = inputs.stats[["pg_id", "pg_gameweek", "pg_points"]]
    grid = grid.merge(stats, left_on=["p_id", "gw"], right_on=["pg_id", "pg_gameweek"], how="left")
    grid["pg_points"] = grid["pg_points"].fillna(0)

    recent = grid[grid["gw"] >= target_gw - FORM_WINDOW_GWS]

    def per_match(frame: pd.DataFrame) -> pd.Series:
        sums = frame.groupby("p_id")[["pg_points", "n_matches"]].sum()
        return sums["pg_points"] / sums["n_matches"].replace(0, np.nan)

    out = pd.DataFrame({"form": per_match(recent), "season": per_match(grid)})
    return out.reindex(inputs.players["p_id"]).fillna(0.0).rename_axis("p_id").reset_index()


def evaluate_gameweek(inputs: ModelInputs, target_gw: int, cfg: ModelConfig) -> pd.DataFrame:
    """Predictions from every method next to actual points for ``target_gw``."""
    cfg = cfg.with_overrides(horizon=1, use_availability=False)
    projection = project(inputs, target_gw, cfg)
    predicted = projection.players[["p_id", "xpts_horizon"]].rename(columns={"xpts_horizon": "model"})

    stats = inputs.stats
    actual = stats[stats["pg_gameweek"] == target_gw].groupby("pg_id")[["pg_points", "pg_minutes"]].sum()
    recent = stats[(stats["pg_gameweek"] < target_gw) & (stats["pg_gameweek"] >= target_gw - 2)]
    recent_minutes = recent.groupby("pg_id")["pg_minutes"].sum()

    frame = predicted.merge(baselines(inputs, target_gw), on="p_id")
    frame["actual"] = frame["p_id"].map(actual["pg_points"]).fillna(0.0)
    minutes_now = frame["p_id"].map(actual["pg_minutes"]).fillna(0)
    minutes_before = frame["p_id"].map(recent_minutes).fillna(0)
    frame = frame[(minutes_now > 0) | (minutes_before > 0)]
    return frame.assign(gw=target_gw)


def score(frame: pd.DataFrame) -> pd.DataFrame:
    """Accuracy metrics per method for one or more gameweeks' predictions."""
    rows = []
    for method in METHODS:
        error = frame[method] - frame["actual"]
        top = frame.sort_values(method, ascending=False).groupby("gw").head(TOP_N)
        rows.append(
            {
                "method": method,
                "MAE": error.abs().mean(),
                "RMSE": np.sqrt((error**2).mean()),
                "rank corr.": frame[method].rank().corr(frame["actual"].rank()),
                f"top-{TOP_N} pts": top["actual"].mean(),
                "bias": error.mean(),
            }
        )
    return pd.DataFrame(rows).set_index("method")


def backtest(
    inputs: ModelInputs, target_gws: list[int], cfg: ModelConfig | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pooled metrics over all ``target_gws`` and the per-player predictions."""
    cfg = cfg or ModelConfig()
    predictions = pd.concat([evaluate_gameweek(inputs, gw, cfg) for gw in target_gws], ignore_index=True)
    return score(predictions), predictions


def default_targets(inputs: ModelInputs, first_gw: int = 2) -> list[int]:
    """Every finished gameweek that has at least one earlier gameweek of data."""
    played = sorted(int(gw) for gw in inputs.stats["pg_gameweek"].unique())
    return [gw for gw in played if gw >= first_gw and any(p < gw for p in played)]


PRIOR_VARIANTS = {
    "current settings": {},
    "no history (price priors only)": {"use_history": False},
    "no history, no prices": {"use_history": False, "price_prior_power": 0.0, "team_price_prior_power": 0.0},
    "history weaker (4 x 90s)": {"history_prior_90s": 4.0},
    "history stronger (16 x 90s)": {"history_prior_90s": 16.0},
    "history stronger (32 x 90s)": {"history_prior_90s": 32.0},
    "history, no fade": {"history_fade": 1.0},
    "history, two seasons (older at half)": {"history_season_weights": (1.0, 0.5)},
}


def compare_priors(inputs: ModelInputs, targets: list[int]) -> pd.DataFrame:
    """The model's backtest metrics under each of PRIOR_VARIANTS."""
    rows = {}
    for name, overrides in PRIOR_VARIANTS.items():
        metrics, _ = backtest(inputs, targets, ModelConfig().with_overrides(**overrides))
        rows[name] = metrics.loc["model"]
    return pd.DataFrame(rows).T


def main() -> None:
    from inputs import load_inputs  # database access only needed from the CLI

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-gw", type=int, default=2, help="first target gameweek (default 2)")
    parser.add_argument(
        "--compare-priors",
        action="store_true",
        help="compare the model's prior settings (history, prices) instead of the baselines",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    inputs = load_inputs()
    targets = default_targets(inputs, args.from_gw)
    if not targets:
        logger.info("Not enough finished gameweeks to backtest yet.")
        return
    if args.compare_priors:
        table = compare_priors(inputs, targets)
        logger.info("Model with different priors, gameweeks %s\n", targets)
        logger.info(table.round(4).to_string())
        return
    metrics, predictions = backtest(inputs, targets)
    logger.info("Backtest over gameweeks %s (%d player-gameweeks)\n", targets, len(predictions))
    logger.info(metrics.round(3).to_string())


if __name__ == "__main__":
    main()
