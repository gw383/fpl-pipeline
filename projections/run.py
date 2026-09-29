"""Project every player's expected points for the upcoming gameweeks and
write them to the warehouse. Runs after ``dbt build``.

    python projections/run.py

Writes three tables to the analytics schema:

* ``player_rating``     -- one row per player: expected points next gameweek
  and over the horizon (split by scoring category), expected minutes and the
  0-10 star rating the dashboard shows;
* ``player_projection`` -- one row per player per upcoming fixture;
* ``team_rating``       -- each team's attack, defence and defensive-actions-allowed multipliers;
* ``player_gameweek_expected`` -- what the model expected from every player in
  each gameweek that has started, predicted from the data before it (so the
  dashboard can show expected next to actual points). Each gameweek is
  computed once, and the latest started one on every run.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime

import pandas as pd

from inputs import load_expected_gameweeks, load_inputs, write_gameweek_expectations, write_projection
from model import ModelConfig, ModelInputs, next_gameweek, project

logger = logging.getLogger(__name__)


def validate(projection) -> None:
    """Fail loudly rather than publish a broken projection."""
    players = projection.players
    problems = []
    if players.empty:
        problems.append("no players projected")
    if players["xpts_horizon"].isna().any():
        problems.append("missing expected points")
    if (players["star"] < 0).any() or (players["star"] > 10).any():
        problems.append("star rating outside 0-10")
    if players["p_id"].duplicated().any():
        problems.append("duplicate players")
    if problems:
        raise ValueError("Projection failed validation: " + "; ".join(problems))


def gameweek_expectations(inputs: ModelInputs, gameweeks: list[int], cfg: ModelConfig | None = None) -> pd.DataFrame:
    """Each player's expected points and minutes in each of ``gameweeks``,
    as the model would have predicted it before that gameweek: only earlier
    data, and without availability flags (past flags aren't stored, and
    today's flags may describe an injury picked up since)."""
    cfg = (cfg or ModelConfig()).with_overrides(horizon=1, use_availability=False)
    frames = []
    for gw in gameweeks:
        players = project(inputs, gw, cfg).players
        frames.append(
            players[["p_id", "xpts_next_gw", "xmins_next_gw"]]
            .rename(columns={"xpts_next_gw": "xpts", "xmins_next_gw": "xmins"})
            .assign(gw=gw)
        )
    columns = ["p_id", "gw", "xpts", "xmins"]
    return pd.concat(frames, ignore_index=True)[columns] if frames else pd.DataFrame(columns=columns)


def started_gameweeks(inputs: ModelInputs, as_of_gw: int | None) -> list[int]:
    """Gameweeks whose deadline has passed."""
    gameweeks = sorted(int(gw) for gw in inputs.gameweeks["gw_id"])
    return [gw for gw in gameweeks if as_of_gw is None or gw < as_of_gw]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    inputs = load_inputs()
    as_of_gw = next_gameweek(inputs.gameweeks, datetime.now(UTC))

    # Expected points for gameweeks already under way: any not stored yet,
    # plus the latest (its prediction is final once its deadline passes, but
    # refreshing it picks up late data fixes before the next deadline).
    started = started_gameweeks(inputs, as_of_gw)
    if started:
        done = load_expected_gameweeks()
        todo = sorted({gw for gw in started if gw not in done} | {started[-1]})
        logger.info("Expected points for started gameweek(s) %s", todo)
        write_gameweek_expectations(gameweek_expectations(inputs, todo))

    if as_of_gw is None:
        logger.info("No upcoming gameweeks -- the season is over, nothing to project.")
        return 0

    projection = project(inputs, as_of_gw, ModelConfig())
    validate(projection)
    write_projection(projection, inputs.players)
    return 0


if __name__ == "__main__":
    sys.exit(main())
