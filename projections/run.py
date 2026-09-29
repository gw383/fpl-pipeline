"""Project every player's expected points for the upcoming gameweeks and
write them to the warehouse. Runs after ``dbt build``.

    python projections/run.py

Writes three tables to the analytics schema:

* ``player_rating``     -- one row per player: expected points next gameweek
  and over the horizon (split by scoring category), expected minutes and the
  0-10 star rating the dashboard shows;
* ``player_projection`` -- one row per player per upcoming fixture;
* ``team_rating``       -- each team's attack, defence and defensive-actions-allowed multipliers.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime

from inputs import load_inputs, write_projection
from model import ModelConfig, next_gameweek, project

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


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    inputs = load_inputs()
    as_of_gw = next_gameweek(inputs.gameweeks, datetime.now(UTC))
    if as_of_gw is None:
        logger.info("No upcoming gameweeks -- the season is over, nothing to project.")
        return 0

    projection = project(inputs, as_of_gw, ModelConfig())
    validate(projection)
    write_projection(projection, inputs.players)
    return 0


if __name__ == "__main__":
    sys.exit(main())
