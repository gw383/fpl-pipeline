"""A small, made-up league in the shape of the warehouse's analytics tables,
for testing the dashboard's data file and queries without SQL Server.

20 teams of 15 players, 38 gameweeks of which the first ``PLAYED`` have
kicked off (deadlines are placed around "now", so the dashboard's
time-based queries see gameweek ``PLAYED`` as current), and two managers.
Values are random but seeded, so every run builds the same league.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

PLAYED = 6  # gameweeks whose deadline has passed
SCHEDULED = 11  # gameweeks with fixtures
MANAGER_ID = 194625
OTHER_MANAGER_ID = 146897

TEAMS = [
    ("Arsenal", "ARS", "arsenal.png", "#EF0107", "#FFFFFF"),
    ("Aston Villa", "AVL", "villa.png", "#670E36", "#95BFE5"),
    ("Bournemouth", "BOU", "bournemouth.png", "#DA291C", "#000000"),
    ("Brentford", "BRE", "brentford.png", "#E30613", "#FFFFFF"),
    ("Brighton", "BHA", "brighton.png", "#0057B8", "#FFFFFF"),
    ("Burnley", "BUR", "burnley.png", "#6C1D45", "#99D6EA"),
    ("Chelsea", "CHE", "chelsea.png", "#034694", "#FFFFFF"),
    ("Coventry", "COV", "coventry.png", "#59CBE8", "#FFFFFF"),
    ("Crystal Palace", "CRY", "palace.png", "#1B458F", "#C4122E"),
    ("Everton", "EVE", "everton.png", "#003399", "#FFFFFF"),
    ("Fulham", "FUL", "fulham.png", "#FFFFFF", "#000000"),
    ("Hull City", "HUL", "hull.png", "#F5A12D", "#000000"),
    ("Ipswich", "IPS", "ipswich.png", "#3A64A3", "#FFFFFF"),
    ("Leeds", "LEE", "leeds.png", "#FFFFFF", "#1D428A"),
    ("Liverpool", "LIV", "liverpool.png", "#C8102E", "#F6EB61"),
    ("Man City", "MCI", "man_city.png", "#6CABDD", "#1C2C5B"),
    ("Man Utd", "MUN", "man_utd.png", "#DA291C", "#FBE122"),
    ("Newcastle", "NEW", "newcastle.png", "#241F20", "#FFFFFF"),
    ("Nott'm Forest", "NFO", "forest.png", "#DD0000", "#FFFFFF"),
    ("Spurs", "TOT", "spuds.png", "#132257", "#FFFFFF"),
]
FIRST_NAMES = ["Bukayo", "Gabriel", "Mohamed", "Cole", "Erling", "Bruno", "Alexander", "Dominic", "Jarrod", "Ollie",
               "Morgan", "Kevin", "Declan", "Trent", "Virgil", "Joško", "Matheus", "Pedro", "Antoine", "Jean-Philippe"]  # fmt: skip
LAST_NAMES = ["Saka", "Magalhães", "Salah", "Palmer", "Haaland", "Fernandes", "Isak", "Calvert-Lewin", "Bowen",
              "Watkins", "Gibbs-White", "De Bruyne", "Rice", "Alexander-Arnold", "van Dijk", "Gvardiol", "Cunha",
              "Neto", "Semenyo", "Mateta", "Mukiele", "Thomas", "Wood", "Mbeumo"]  # fmt: skip
POSITION_NAMES = {1: "Goalkeeper", 2: "Defender", 3: "Midfielder", 4: "Forward"}
SQUAD_POSITIONS = [1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4]  # one team's 15 players
NEWS = ["Hamstring injury - 75% chance of playing", "Knock - Unknown return date", "Suspended until 18 Oct"]


def _gameweeks(now: dt.datetime) -> pd.DataFrame:
    ids = np.arange(1, 39)
    # Gameweek PLAYED's deadline was half a week ago; the next is half a week away.
    deadlines = [now + dt.timedelta(weeks=float(gw) - PLAYED - 0.5) for gw in ids]
    return pd.DataFrame(
        {
            "gw_id": ids,
            "gw_name": [f"Gameweek {gw}" for gw in ids],
            "gw_deadline_time": pd.to_datetime(deadlines).floor("s"),
            "gw_offset": 38 - ids,
        }
    )


def _teams(rng: np.random.Generator) -> pd.DataFrame:
    teams = pd.DataFrame(
        TEAMS,
        columns=["team_name", "team_short_name", "team_badge_file", "team_primary_colour", "team_secondary_colour"],
    )
    teams.insert(0, "team_id", np.arange(1, len(teams) + 1))
    teams["team_code"] = teams["team_id"] + 100
    teams["team_table_position"] = rng.permutation(len(teams)) + 1
    teams["team_strength"] = rng.integers(2, 6, len(teams))
    return teams


def _players(rng: np.random.Generator, teams: pd.DataFrame, now: dt.datetime) -> pd.DataFrame:
    rows = []
    for team_id in teams["team_id"]:
        for position in SQUAD_POSITIONS:
            player_id = len(rows) + 1
            last = LAST_NAMES[int(rng.integers(len(LAST_NAMES)))]
            has_news = rng.random() < 0.08
            price = round(float(rng.uniform(4.0, 14.5)), 1)
            rows.append(
                {
                    "p_id": player_id,
                    "p_web_name": last,
                    "p_full_name": f"{FIRST_NAMES[int(rng.integers(len(FIRST_NAMES)))]} {last}",
                    "p_team": int(team_id),
                    "p_position": position,
                    "p_position_name": POSITION_NAMES[position],
                    "p_price": price,
                    "p_start_price": price,
                    "p_ownership": round(float(rng.uniform(0.5, 60)), 1),
                    # FPL sends form as text, and the warehouse keeps it that way.
                    "p_form": f"{rng.uniform(0, 12):.1f}",
                    "p_creativity": round(float(rng.uniform(0, 300)), 1),
                    "p_threat": round(float(rng.uniform(0, 300)), 1),
                    "p_influence": round(float(rng.uniform(0, 300)), 1),
                    "p_news": NEWS[int(rng.integers(len(NEWS)))] if has_news else "",
                    "p_news_date": (
                        (now - dt.timedelta(hours=int(rng.integers(1, 200)))).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                        if has_news
                        else None
                    ),
                    "p_status": "d" if has_news else "a",
                    "p_code": 10_000 + player_id,
                    "p_penalties_order": 1.0 if position == 4 and rng.random() < 0.3 else None,
                    "p_corners_order": None,
                    "p_direct_freekicks_order": None,
                    "p_chance_of_playing": 75.0 if has_news else None,
                }
            )
    return pd.DataFrame(rows)


def _fixtures(rng: np.random.Generator, teams: pd.DataFrame) -> pd.DataFrame:
    rows = []
    team_ids = teams["team_id"].to_numpy()
    for gw in range(1, SCHEDULED + 1):
        order = rng.permutation(team_ids)
        for home, away in zip(order[::2], order[1::2], strict=True):
            finished = gw <= PLAYED
            rows.append(
                {
                    "f_id": len(rows) + 1,
                    "f_gameweek": gw,
                    "f_away_team": int(away),
                    "f_home_team": int(home),
                    "f_away_score": float(rng.integers(0, 4)) if finished else None,
                    "f_home_score": float(rng.integers(0, 4)) if finished else None,
                    "f_home_diff": int(rng.integers(2, 6)),
                    "f_away_diff": int(rng.integers(2, 6)),
                    "f_finished": finished,
                }
            )
    return pd.DataFrame(rows)


def _player_stats(rng: np.random.Generator, players: pd.DataFrame) -> pd.DataFrame:
    n = len(players) * PLAYED
    minutes = rng.choice([0, 20, 60, 90], size=n, p=[0.25, 0.1, 0.15, 0.5])
    played = minutes > 0
    stats = pd.DataFrame(
        {
            "pg_id": np.repeat(players["p_id"].to_numpy(), PLAYED),
            "pg_points": np.where(played, rng.integers(0, 15, n), 0),
            "pg_goals": np.where(played, rng.integers(0, 3, n), 0),
            "pg_assists": np.where(played, rng.integers(0, 3, n), 0),
            "pg_minutes": minutes,
            "pg_clean_sheets": np.where(minutes >= 60, rng.integers(0, 2, n), 0),
            "pg_goals_conceded": np.where(played, rng.integers(0, 4, n), 0),
            "pg_own_goals": 0,
            "pg_pens_saved": 0,
            "pg_pens_missed": 0,
            "pg_yellow_cards": np.where(played, rng.integers(0, 2, n), 0),
            "pg_red_cards": 0,
            "pg_saves": np.where(played, rng.integers(0, 7, n), 0),
            "pg_bonus": np.where(played, rng.integers(0, 4, n), 0),
            "pg_bps": np.where(played, rng.integers(0, 40, n), 0),
            "pg_influence": rng.uniform(0, 60, n).round(1),
            "pg_creativity": rng.uniform(0, 60, n).round(1),
            "pg_threat": rng.uniform(0, 60, n).round(1),
            "pg_ict": rng.uniform(0, 18, n).round(1),
            "pg_defcons": np.where(played, rng.integers(0, 16, n), 0),
            "pg_starts": (minutes >= 60).astype(int),
            # Mixed-case names, as dbt declares them in the warehouse.
            "pg_xG": np.where(played, rng.uniform(0, 1.2, n), 0).round(2),
            "pg_xA": np.where(played, rng.uniform(0, 0.8, n), 0).round(2),
            "pg_XGI": np.where(played, rng.uniform(0, 2, n), 0).round(2),
            "pg_xGa": np.where(played, rng.uniform(0, 2.5, n), 0).round(2),
            "pg_dreamteam": False,
            "pg_played": played,
            "pg_gameweek": np.tile(np.arange(1, PLAYED + 1), len(players)),
        }
    )
    # Goalkeepers save penalties now and then.
    keepers = stats["pg_id"].isin(players.loc[players["p_position"] == 1, "p_id"]) & played
    stats.loc[keepers, "pg_pens_saved"] = rng.integers(0, 2, int(keepers.sum()))
    return stats


def _player_points(stats: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    position = stats["pg_id"].map(players.set_index("p_id")["p_position"])
    return pd.DataFrame(
        {
            "pg_id": stats["pg_id"],
            "pg_gameweek": stats["pg_gameweek"],
            "pg_points": stats["pg_points"],
            "pg_starts": stats["pg_starts"],
            "p_position": position,
            "pf_minutes": np.select([stats["pg_minutes"] >= 60, stats["pg_minutes"] > 0], [2, 1], 0),
            "pf_cs": np.where(position <= 2, 4, np.where(position == 3, 1, 0)) * stats["pg_clean_sheets"],
            "pf_bonus": stats["pg_bonus"],
            "pf_saves": np.floor(stats["pg_saves"] / 3.0),
            "pf_pen_saves": stats["pg_pens_saved"] * 5,
            "pf_yellow": -stats["pg_yellow_cards"],
            "pf_red": -stats["pg_red_cards"] * 3,
            "pf_goals_conceded": np.where(position <= 2, -(stats["pg_goals_conceded"] // 2), 0),
            "pf_goals": stats["pg_goals"] * position.map({1: 10, 2: 6, 3: 5, 4: 4}),
            "pf_assists": stats["pg_assists"] * 3,
            "pf_defcon": np.where(stats["pg_defcons"] >= 10, 2, 0),
            "pf_own_goals": -stats["pg_own_goals"] * 2,
            "pf_pen_missed": -stats["pg_pens_missed"] * 2,
        }
    )


def _player_rating(rng: np.random.Generator, players: pd.DataFrame) -> pd.DataFrame:
    n = len(players)
    star = rng.uniform(1.5, 10, n).round(1)
    horizon = (star * 3.2).round(2)
    rating = pd.DataFrame(
        {
            "p_id": players["p_id"],
            "player": players["p_full_name"],
            "p_position": players["p_position"],
            "p_penalties_order": players["p_penalties_order"],
            "star": star,
            "xpts_next_gw": (star * 0.7).round(2),
            "xpts_horizon": horizon,
            "xpts_per_gw": (horizon / 5).round(2),
            "xmins_next_gw": rng.choice([15.0, 55.0, 80.0, 88.0], n),
            "availability_next_gw": np.where(players["p_news"] != "", 0.75, 1.0),
            "fixtures_in_horizon": 5,
            "pts_appearance": 9.0,
            "pts_goals": rng.uniform(0, 8, n).round(2),
            "pts_assists": rng.uniform(0, 5, n).round(2),
            "pts_penalties": np.where(players["p_penalties_order"].notna(), 1.4, 0.0),
            "pts_clean_sheet": rng.uniform(0, 4, n).round(2),
            "pts_goals_conceded": -1.0,
            "pts_saves": np.where(players["p_position"] == 1, 2.5, 0.0),
            "pts_defcon": rng.uniform(0, 3, n).round(2),
            "pts_bonus": rng.uniform(0, 3, n).round(2),
            "pts_cards": -0.3,
            "xg_horizon": rng.uniform(0, 3, n).round(2),
            "xa_horizon": rng.uniform(0, 2, n).round(2),
            "xpens_horizon": np.where(players["p_penalties_order"].notna(), 0.6, 0.0),
            "star_typical_xpts": 3.6,
            "star_best_xpts": 8.1,
        }
    )
    rating["position_rank"] = (
        rating.groupby("p_position")["xpts_horizon"].rank(ascending=False, method="first").astype(int)
    )
    return rating


def _team_fixture_results(rng: np.random.Generator, fixtures: pd.DataFrame) -> pd.DataFrame:
    finished = fixtures[fixtures["f_finished"]]
    sides = []
    for venue, own, opp in (("H", "home", "away"), ("A", "away", "home")):
        sides.append(
            pd.DataFrame(
                {
                    "f_id": finished["f_id"],
                    "team_id": finished[f"f_{own}_team"],
                    "gw_id": finished["f_gameweek"],
                    "venue": venue,
                    "opponent_id": finished[f"f_{opp}_team"],
                    "own_score": finished[f"f_{own}_score"].astype(int),
                    "opp_score": finished[f"f_{opp}_score"].astype(int),
                }
            )
        )
    results = pd.concat(sides, ignore_index=True)
    results["result"] = np.select(
        [results["own_score"] > results["opp_score"], results["own_score"] < results["opp_score"]], ["W", "L"], "D"
    )
    for column in ("team_xg", "team_xa", "team_xga"):
        results[column] = rng.uniform(0.3, 2.6, len(results)).round(2)
    results["fixtures_in_gw"] = 1
    results["is_double_gw"] = 0
    return results


def _managers(rng: np.random.Generator, players: pd.DataFrame, teams: pd.DataFrame, now: dt.datetime) -> dict:
    profile = pd.DataFrame(
        {
            "m_id": [MANAGER_ID, OTHER_MANAGER_ID],
            "m_player_name": ["George Williams", "Sam Friend"],
            "m_team_name": ["Pep Talk FC", "Haaland Grand"],
            "m_overall_points": [412, 388],
            "m_overall_rank": [123_456, 987_654],
            "m_squad_value": [1024, 1003],
            "m_bank": [12, 5],
            "m_loaded_at": pd.to_datetime([now - dt.timedelta(hours=3)] * 2).floor("s"),
        }
    )
    team_lookup = teams.set_index("team_id")
    squads, history, transfers = [], [], []
    for manager in profile["m_id"]:
        picks = []
        # 2 goalkeepers, 5 defenders, 5 midfielders, 3 forwards; a 4-4-2 starts.
        for position, count in ((1, 2), (2, 5), (3, 5), (4, 3)):
            pool = players[players["p_position"] == position]
            picks += list(pool.sample(count, random_state=int(rng.integers(1_000_000)))["p_id"])
        by_id = players.set_index("p_id")
        starters = [picks[0], *picks[2:6], *picks[7:11], *picks[12:14]]
        bench = [picks[1], picks[6], picks[11], picks[14]]
        for slot, player_id in enumerate([*starters, *bench], start=1):
            player = by_id.loc[player_id]
            team = team_lookup.loc[player["p_team"]]
            squads.append(
                {
                    "m_id": manager,
                    "gw_id": PLAYED,
                    "squad_position": slot,
                    "is_starting": int(slot <= 11),
                    "is_captain": slot == 10,
                    "is_vice_captain": slot == 7,
                    "multiplier": 2 if slot == 10 else int(slot <= 11),
                    "p_id": int(player_id),
                    "player": player["p_full_name"],
                    "web_name": player["p_web_name"],
                    "p_position": int(player["p_position"]),
                    "team_id": int(player["p_team"]),
                    "team_name": team["team_name"],
                    "team_short_name": team["team_short_name"],
                }
            )
        for gw in range(1, PLAYED + 1):
            history.append(
                {
                    "m_id": manager,
                    "gw_id": gw,
                    "gw_points": int(rng.integers(35, 90)),
                    "total_points": 60 * gw,
                    "overall_rank": int(rng.integers(50_000, 2_000_000)),
                    "bank": 12,
                    "squad_value": 1000 + gw * 4,
                    "transfers_made": int(gw > 1),
                    "transfers_cost": 4 if gw == PLAYED else 0,
                    "points_on_bench": int(rng.integers(0, 15)),
                    "active_chip": "wildcard" if gw == 3 else None,
                }
            )
        for i in range(12):
            player_in, player_out = players.sample(2, random_state=int(rng.integers(1_000_000))).itertuples()
            transfers.append(
                {
                    "m_id": manager,
                    "gw_id": max(2, PLAYED - i // 2),
                    "transfer_time": (now - dt.timedelta(days=i * 3, hours=2)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "player_in": player_in.p_full_name,
                    "player_in_position": player_in.p_position,
                    "player_out": player_out.p_full_name,
                    "player_out_position": player_out.p_position,
                }
            )
    return {
        "manager_profile": profile,
        "manager_squad": pd.DataFrame(squads),
        "manager_gameweek_history": pd.DataFrame(history),
        "manager_transfers": pd.DataFrame(transfers),
    }


def build(now: dt.datetime | None = None, seed: int = 7) -> dict[str, pd.DataFrame]:
    """Every table the data file holds, keyed by table name."""
    now = (now or dt.datetime.now(dt.UTC)).replace(tzinfo=None)
    rng = np.random.default_rng(seed)
    teams = _teams(rng)
    players = _players(rng, teams, now)
    fixtures = _fixtures(rng, teams)
    stats = _player_stats(rng, players)
    rating = _player_rating(rng, players)
    return {
        "gameweeks": _gameweeks(now),
        "fixtures": fixtures,
        "teams": teams,
        "players": players,
        "player_stats": stats,
        "player_points": _player_points(stats, players),
        "player_rating": rating,
        "team_fixture_results": _team_fixture_results(rng, fixtures),
        **_managers(rng, players, teams, now),
        "player_gameweek_expected": pd.DataFrame(
            {
                "p_id": np.repeat(players["p_id"].to_numpy(), PLAYED),
                "gw": np.tile(np.arange(1, PLAYED + 1), len(players)),
                "xpts": np.repeat((rating["star"] * 0.6).round(2).to_numpy(), PLAYED),
                "xmins": 80.0,
            }
        ),
    }
