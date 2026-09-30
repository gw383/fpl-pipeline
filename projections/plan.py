"""Plan a squad from the projections: the best 15 for a wildcard (or a new
team), or the best transfers for a manager's current squad.

Unlike run.py this writes nothing to the warehouse -- it prints a plan (and
optionally saves it as CSV), so you can look further ahead for a wildcard
without changing what the dashboard shows.

    # Wildcard: best 15 over the next 8 gameweeks, on your own budget
    python projections/plan.py wildcard --manager 194625 --horizon 8

    # Weekly: best use of this week's free transfer(s) over the next 4
    python projections/plan.py transfers --manager 194625 --free-transfers 1

    # Treat a flagged player as fit (by FPL ID or web name)
    python projections/plan.py wildcard --budget 100 --assume-fit "João Pedro"

Later gameweeks count for less (``--discount``): projections further out
are less certain, and you'll make transfers along the way anyway. Every
gameweek the best eleven and captain are picked from the fifteen; bench
points count for 10% (they only matter when someone doesn't play).

The squad is chosen with an integer programme: 2 GK, 5 DEF, 5 MID, 3 FWD,
at most 3 per club, within budget, a valid formation every week.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from model import ModelConfig, ModelInputs, next_gameweek, project

logger = logging.getLogger(__name__)

SQUAD = {1: 2, 2: 5, 3: 5, 4: 3}  # players per position
FORMATION = {1: (1, 1), 2: (3, 5), 3: (2, 5), 4: (1, 3)}  # starters per position (min, max)
MAX_PER_CLUB = 3
BENCH_WEIGHT = 0.1
HIT_COST = 4
POSITION_NAMES = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


# ---------------------------------------------------------------------------
# Points per gameweek
# ---------------------------------------------------------------------------


def gameweek_points(projection, discount: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Expected points per player per gameweek (p_id x gw, blanks as 0, a
    double gameweek's two fixtures summed): raw, and weighted by
    ``discount ** weeks ahead``."""
    raw = projection.fixtures.groupby(["p_id", "gw"])["xpts"].sum().unstack(fill_value=0.0)
    raw = raw.reindex(columns=projection.horizon_gws, fill_value=0.0)
    weights = pd.Series([discount**i for i in range(len(projection.horizon_gws))], index=projection.horizon_gws)
    return raw, raw * weights


# ---------------------------------------------------------------------------
# The optimiser
# ---------------------------------------------------------------------------


@dataclass
class Plan:
    squad: pd.DataFrame  # the 15, with price and expected points per gameweek
    lineups: dict[int, dict] = field(default_factory=dict)  # gw -> {"starters", "captain", "bench"}
    transfers_in: list[int] = field(default_factory=list)
    transfers_out: list[int] = field(default_factory=list)
    hits: int = 0
    objective: float = 0.0  # weighted points of the eleven + captain + bench share, minus hits


def candidate_pool(players: pd.DataFrame, points: pd.DataFrame, keep: set[int], per_position: int = 40) -> list[int]:
    """The players worth considering: the best ``per_position`` in each
    position by weighted points, the cheapest eight in each (budget
    fillers), and anyone in ``keep`` (the current squad)."""
    frame = players.assign(total=players["p_id"].map(points.sum(axis=1)).fillna(0.0))
    chosen = set(keep)
    for _, group in frame.groupby("p_position"):
        chosen |= set(group.nlargest(per_position, "total")["p_id"])
        chosen |= set(group.sort_values(["price", "total"], ascending=[True, False]).head(8)["p_id"])
    return sorted(chosen)


def optimise(
    players: pd.DataFrame,
    points: pd.DataFrame,
    budget: float,
    current: list[int] | None = None,
    free_transfers: int = 1,
    max_transfers: int | None = None,
    bench_weight: float = BENCH_WEIGHT,
    hit_cost: float = HIT_COST,
    time_limit: float = 120.0,
    locked: set[int] | None = None,
    max_per_club: int = MAX_PER_CLUB,
) -> Plan:
    """The best 15-man squad for the weighted ``points`` (p_id x gw).

    ``players`` needs p_id, p_position, p_team and price. With ``current``
    (the 15 you own) it plans transfers: players not in ``current`` are
    transfers in, each beyond ``free_transfers`` costs ``hit_cost`` points,
    and at most ``max_transfers`` are allowed. Players in ``locked`` must be
    in the squad.
    """
    current = list(current or [])
    locked = set(locked or ())
    pool = candidate_pool(players, points, set(current) | locked)
    info = players.set_index("p_id").loc[pool]
    pts = points.reindex(pool).fillna(0.0).to_numpy()
    n, n_gw = pts.shape
    gws = list(points.columns)

    # Variables: squad x[i], starter s[i, g], captain c[i, g], then hits h.
    def x(i):
        return i

    def s(i, g):
        return n + i * n_gw + g

    def c(i, g):
        return n + n * n_gw + i * n_gw + g

    hits_var = n + 2 * n * n_gw
    n_vars = hits_var + 1

    objective = np.zeros(n_vars)
    for i in range(n):
        objective[x(i)] -= bench_weight * pts[i].sum()
        for g in range(n_gw):
            objective[s(i, g)] -= (1 - bench_weight) * pts[i, g]
            objective[c(i, g)] -= pts[i, g]
    objective[hits_var] = hit_cost

    rows: list[dict[int, float]] = []
    lower: list[float] = []
    upper: list[float] = []

    def add(coefficients: dict[int, float], lo: float, hi: float) -> None:
        rows.append(coefficients)
        lower.append(lo)
        upper.append(hi)

    position = info["p_position"].to_numpy()
    club = info["p_team"].to_numpy()
    price = info["price"].to_numpy()
    add({x(i): price[i] for i in range(n)}, 0, budget + 1e-6)
    for pos, count in SQUAD.items():
        add({x(i): 1 for i in range(n) if position[i] == pos}, count, count)
    for team in set(club):
        add({x(i): 1 for i in range(n) if club[i] == team}, 0, max_per_club)
    for i, p_id in enumerate(pool):
        if p_id in locked:
            add({x(i): 1}, 1, 1)
    for g in range(n_gw):
        add({s(i, g): 1 for i in range(n)}, 11, 11)
        add({c(i, g): 1 for i in range(n)}, 1, 1)
        for pos, (lo, hi) in FORMATION.items():
            add({s(i, g): 1 for i in range(n) if position[i] == pos}, lo, hi)
        for i in range(n):
            add({s(i, g): 1, x(i): -1}, -np.inf, 0)
            add({c(i, g): 1, s(i, g): -1}, -np.inf, 0)

    owned = set(current)
    new_players = {x(i): 1 for i, p_id in enumerate(pool) if p_id not in owned}
    if current:
        # hits >= transfers in - free transfers
        add({**new_players, hits_var: -1}, -np.inf, free_transfers)
        if max_transfers is not None:
            add(new_players, 0, max_transfers)
    else:
        add({hits_var: 1}, 0, 0)

    matrix = lil_matrix((len(rows), n_vars))
    for r, coefficients in enumerate(rows):
        for j, value in coefficients.items():
            matrix[r, j] = value
    upper_bounds = np.ones(n_vars)
    upper_bounds[hits_var] = 15
    result = milp(
        objective,
        constraints=LinearConstraint(matrix.tocsr(), lower, upper),
        integrality=np.ones(n_vars),
        bounds=Bounds(np.zeros(n_vars), upper_bounds),
        options={"time_limit": time_limit},
    )
    if result.x is None:
        raise RuntimeError(
            f"No valid squad found ({result.message}). Is the budget too low, or are too many players locked?"
        )
    chosen = result.x > 0.5

    squad_ids = [p_id for i, p_id in enumerate(pool) if chosen[x(i)]]
    lineups = {}
    for g, gw in enumerate(gws):
        starters = [p_id for i, p_id in enumerate(pool) if chosen[s(i, g)]]
        captain = next(p_id for i, p_id in enumerate(pool) if chosen[c(i, g)])
        bench = [p for p in squad_ids if p not in starters]
        lineups[gw] = {"starters": starters, "captain": captain, "bench": bench}

    squad = info.loc[squad_ids].reset_index()
    return Plan(
        squad=squad,
        lineups=lineups,
        transfers_in=[p for p in squad_ids if p not in owned] if current else [],
        transfers_out=[p for p in current if p not in squad_ids],
        hits=int(round(result.x[hits_var])),
        objective=-float(result.fun),
    )


def best_lineups(squad: list[int], points: pd.DataFrame, positions: pd.Series) -> dict[int, dict]:
    """The best valid eleven and captain each gameweek for a fixed 15:
    every legal formation is tried with the top-scoring players in each
    position (exact for a fixed squad, and instant)."""
    pos = positions.reindex(squad)
    lineups = {}
    for gw in points.columns:
        pts = points[gw].reindex(squad).fillna(0.0)
        ranked = {p: list(pts[pos == p].sort_values(ascending=False).index) for p in (1, 2, 3, 4)}
        best, best_total = None, -np.inf
        for d in range(FORMATION[2][0], FORMATION[2][1] + 1):
            for m in range(FORMATION[3][0], FORMATION[3][1] + 1):
                f = 10 - d - m
                if not FORMATION[4][0] <= f <= FORMATION[4][1]:
                    continue
                starters = ranked[1][:1] + ranked[2][:d] + ranked[3][:m] + ranked[4][:f]
                if len(starters) != 11:
                    continue
                total = (1 - BENCH_WEIGHT) * pts[starters].sum() + pts[starters].max()  # as optimise() scores it
                if total > best_total:
                    best, best_total = starters, total
        if best is None:
            raise ValueError("The squad can't field a valid eleven (it needs 2 GK, 5 DEF, 5 MID and 3 FWD).")
        captain = pts[best].idxmax()
        lineups[gw] = {"starters": best, "captain": captain, "bench": [p for p in squad if p not in best]}
    return lineups


def evaluate(players: pd.DataFrame, points: pd.DataFrame, squad: list[int]) -> Plan:
    """The best eleven and captain each gameweek for a fixed 15 (no
    transfers; budget and club limits aren't checked) -- how a squad you've
    put together yourself is expected to do."""
    positions = players.set_index("p_id")["p_position"]
    lineups = best_lineups(list(squad), points, positions)
    objective = sum(
        (1 - BENCH_WEIGHT) * points.loc[lineup["starters"], gw].sum()
        + points.loc[lineup["captain"], gw]
        + BENCH_WEIGHT * points.loc[list(squad), gw].sum()
        for gw, lineup in lineups.items()
    )
    return Plan(
        squad=players.set_index("p_id").loc[list(squad)].reset_index(), lineups=lineups, objective=float(objective)
    )


def weekly_summary(plan: Plan, raw: pd.DataFrame, positions: pd.Series) -> pd.DataFrame:
    """One row per gameweek: formation, captain and expected points of the
    eleven with the captain doubled (unweighted)."""
    rows = []
    for gw, lineup in plan.lineups.items():
        counts = positions.reindex(lineup["starters"]).value_counts()
        rows.append(
            {
                "gw": gw,
                "formation": "-".join(str(int(counts.get(p, 0))) for p in (2, 3, 4)),
                "captain": lineup["captain"],
                "points": float(raw.loc[lineup["starters"], gw].sum() + raw.loc[lineup["captain"], gw]),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Reading the warehouse and printing the plan
# ---------------------------------------------------------------------------


def resolve_players(players: pd.DataFrame, names: list[str]) -> set[int]:
    """FPL IDs for a list of IDs or web names (case-insensitive)."""
    ids = set()
    for name in names:
        name = name.strip()
        if name.isdigit():
            ids.add(int(name))
            continue
        match = players[players["p_web_name"].str.casefold() == name.casefold()]
        if match.empty:
            raise SystemExit(f"No player called {name!r}")
        ids |= set(match["p_id"])
    return ids


def load_team_names() -> pd.Series:
    """Team short names by team ID."""
    from sqlalchemy import text

    from inputs import get_engine

    with get_engine().connect() as conn:
        teams = pd.read_sql(text("select team_id, team_short_name from analytics.teams"), conn)
    teams.columns = [c.lower() for c in teams.columns]
    return teams.set_index("team_id")["team_short_name"]


def load_manager(entry_id: int) -> tuple[list[int], float]:
    """A manager's current 15 (analytics.manager_squad) and their squad value
    + bank in £m. Current prices stand in for selling prices, which FPL
    doesn't expose; a player you've made a profit on sells for a little less."""
    from sqlalchemy import text

    from inputs import get_engine

    with get_engine().connect() as conn:
        squad = pd.read_sql(
            text("select p_id from analytics.manager_squad where m_id = :m"), conn, params={"m": entry_id}
        )
        profile = pd.read_sql(
            text("select m_bank from analytics.manager_profile where m_id = :m"), conn, params={"m": entry_id}
        )
    if squad.empty or profile.empty:
        raise SystemExit(f"Manager {entry_id} isn't in the warehouse -- look them up on the My Team page first.")
    squad.columns = [c.lower() for c in squad.columns]
    profile.columns = [c.lower() for c in profile.columns]
    return [int(p) for p in squad["p_id"]], float(profile["m_bank"].iloc[0] or 0) / 10


def describe(plan: Plan, players: pd.DataFrame, raw: pd.DataFrame, names: pd.Series) -> str:
    """The plan as text: the squad by position, each week's team, transfers."""
    gws = list(raw.columns)
    squad = plan.squad.assign(
        name=plan.squad["p_id"].map(names),
        pos=plan.squad["p_position"].map(POSITION_NAMES),
        **{f"GW{gw}": plan.squad["p_id"].map(raw[gw]).round(1) for gw in gws},
    )
    squad["total"] = squad[[f"GW{gw}" for gw in gws]].sum(axis=1).round(1)
    squad = squad.sort_values(["p_position", "total"], ascending=[True, False])
    lines = [
        f"Squad: £{squad['price'].sum():.1f}m",
        squad[["pos", "name", "team", "price", *[f"GW{gw}" for gw in gws], "total"]].to_string(index=False),
        "",
    ]
    for gw, lineup in plan.lineups.items():
        starters = players.set_index("p_id").loc[lineup["starters"], "p_position"].value_counts()
        formation = "-".join(str(starters.get(p, 0)) for p in (2, 3, 4))
        xi = raw.loc[lineup["starters"], gw].sum() + raw.loc[lineup["captain"], gw]
        lines.append(
            f"GW{gw}: {formation}, captain {names[lineup['captain']]}, bench "
            f"{', '.join(names[p] for p in lineup['bench'])} -- {xi:.1f} expected"
        )
    if plan.transfers_out or plan.transfers_in:
        lines += [
            "",
            "Transfers out: " + ", ".join(names[p] for p in plan.transfers_out),
            "Transfers in:  " + ", ".join(names[p] for p in plan.transfers_in),
            f"Hits: {plan.hits} (-{plan.hits * HIT_COST} pts)",
        ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["wildcard", "transfers"])
    parser.add_argument("--manager", type=int, help="FPL manager ID (your squad and budget come from the warehouse)")
    parser.add_argument(
        "--budget", type=float, help="£m to spend (wildcard; default: the manager's value + bank, or 100)"
    )
    parser.add_argument("--horizon", type=int, help="gameweeks to plan over (default 8 for wildcard, 4 for transfers)")
    parser.add_argument("--discount", type=float, help="weight per gameweek further ahead (default 0.9 / 0.85)")
    parser.add_argument("--free-transfers", type=int, default=1)
    parser.add_argument("--max-transfers", type=int, default=2, help="most transfers to consider (transfers mode)")
    parser.add_argument("--assume-fit", nargs="*", default=[], help="players (IDs or web names) to treat as fully fit")
    parser.add_argument("--exclude", nargs="*", default=[], help="players (IDs or web names) never to pick")
    parser.add_argument("--csv", help="also save the squad to this CSV file")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from inputs import load_inputs

    wildcard = args.mode == "wildcard"
    horizon = args.horizon or (8 if wildcard else 4)
    discount = args.discount if args.discount is not None else (0.9 if wildcard else 0.85)

    inputs: ModelInputs = load_inputs()
    as_of_gw = next_gameweek(inputs.gameweeks, datetime.now(UTC))
    if as_of_gw is None:
        logger.info("No upcoming gameweeks.")
        return 0
    fit = frozenset(resolve_players(inputs.players, args.assume_fit))
    projection = project(inputs, as_of_gw, ModelConfig(horizon=horizon, fit_players=fit))
    raw, weighted = gameweek_points(projection, discount)

    players = inputs.players.assign(price=inputs.players["p_price"])
    players = players[~players["p_id"].isin(resolve_players(players, args.exclude))]
    players = players[players["p_status"].fillna("a").ne("u") | players["p_id"].isin(fit)]
    names = inputs.players.set_index("p_id")["p_web_name"]

    current, bank = load_manager(args.manager) if args.manager else ([], 0.0)
    if not wildcard and not current:
        raise SystemExit("Transfers mode needs --manager.")
    squad_value = float(players.set_index("p_id").reindex(current)["price"].sum()) if current else 0.0
    budget = args.budget or (squad_value + bank if current else 100.0)

    logger.info(
        "Planning GW%s-%s (discount %.2f per week), budget £%.1fm", raw.columns[0], raw.columns[-1], discount, budget
    )
    if wildcard:
        plan = optimise(players, weighted, budget)
    else:
        plan = optimise(players, weighted, budget, current, args.free_transfers, args.max_transfers)
        keep = optimise(players, weighted, budget, current, args.free_transfers, 0)
        gain = plan.objective - keep.objective
        logger.info(
            "Rolling the transfer instead: %.1f weighted points; this plan: %.1f (%+.1f)",
            keep.objective,
            plan.objective,
            gain,
        )

    plan.squad["team"] = plan.squad["p_team"].map(load_team_names())
    logger.info("\n%s", describe(plan, players, raw, names))
    if args.csv:
        plan.squad.assign(name=plan.squad["p_id"].map(names)).to_csv(args.csv, index=False)
        logger.info("Saved %s", args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
