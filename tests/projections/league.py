"""A small synthetic league shared by the projection tests."""

import numpy as np
import pandas as pd

from model import ModelInputs

# Four teams; team 1 creates lots of xG and concedes little, team 4 the reverse.
TEAM_XG = {1: 2.4, 2: 1.4, 3: 1.2, 4: 0.6}


def league(n_played: int = 4, n_future: int = 5, extra_fixtures=()) -> ModelInputs:
    """A round-robin-ish league: each played gameweek, 1v4 and 2v3 (venues
    alternating), one starting player per position per team."""
    fixtures, stats, players = [], [], []
    fid = 0
    for gw in range(1, n_played + n_future + 1):
        pairs = [(1, 4), (2, 3)] if gw % 2 else [(4, 1), (3, 2)]
        if gw % 3 == 0:
            pairs = [(1, 3), (2, 4)]
        for home, away in pairs:
            fid += 1
            fixtures.append((fid, gw, home, away))
    for extra in extra_fixtures:
        fid += 1
        fixtures.append((fid, *extra))

    pid = 0
    for team in TEAM_XG:
        for position in (1, 2, 3, 4):
            pid += 1
            players.append((pid, team, position, "a", np.nan, ""))
            for gw in range(1, n_played + 1):
                share = {1: 0.0, 2: 0.1, 3: 0.3, 4: 0.6}[position]
                stats.append(
                    (pid, gw, 90, 1, TEAM_XG[team] * share, 0.1 * position, 8.0 if position == 2 else 3.0,
                     3.0 if position == 1 else 0.0, 0.5, 0.1, float((pid * gw) % 9),
                     10.0 + 4 * position + (pid * gw) % 12, 1 if position == 4 and gw % 2 else 0, 0,
                     1 if team == 1 else 0, 1 if team == 4 else 0, 0)
                )  # fmt: skip

    return ModelInputs(
        players=pd.DataFrame(
            players, columns=["p_id", "p_team", "p_position", "p_status", "p_chance_of_playing", "p_news"]
        ),
        fixtures=pd.DataFrame(fixtures, columns=["f_id", "f_gameweek", "f_home_team", "f_away_team"]),
        gameweeks=pd.DataFrame(
            {
                "gw_id": range(1, n_played + n_future + 1),
                "gw_deadline_time": pd.date_range("2026-08-15", periods=n_played + n_future, freq="7D", tz="UTC"),
            }
        ),
        stats=pd.DataFrame(
            stats,
            columns=[
                "pg_id",
                "pg_gameweek",
                "pg_minutes",
                "pg_starts",
                "pg_xg",
                "pg_xa",
                "pg_defcons",
                "pg_saves",
                "pg_bonus",
                "pg_yellow_cards",
                "pg_points",
                "pg_bps",
                "pg_goals",
                "pg_assists",
                "pg_clean_sheets",
                "pg_goals_conceded",
                "pg_pens_missed",
            ],
        ),  # fmt: skip
    )
