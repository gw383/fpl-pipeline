"""Every dashboard query, run against a data file built from the made-up
league in sample_data.py, and checked against the same answer worked out
in pandas.

These need Streamlit (the query functions are cached with it); they are
skipped where it isn't installed.
"""

import os

import numpy as np
import pandas as pd
import pytest

st = pytest.importorskip("streamlit")

import database  # noqa: E402
import sample_data  # noqa: E402
from data_file import write_data_file  # noqa: E402
from queries import manager_data, player_info, player_stats, team_data, team_results  # noqa: E402
from queries.player_stats import PER_90_MIN_MINUTES, PER_90_MIN_SHARE  # noqa: E402
from sample_data import MANAGER_ID, PLAYED  # noqa: E402

RANGES = {"All gameweeks": None, "Last 10 gameweeks": 10, "Last 5 gameweeks": 5}


def _use(path) -> None:
    """Point the dashboard at ``path`` and forget anything cached."""
    os.environ["FPL_DATA_FILE"] = str(path)
    st.cache_data.clear()
    st.cache_resource.clear()
    database._served_version = None


@pytest.fixture(scope="module")
def league(tmp_path_factory):
    """The made-up league's tables, with the dashboard reading its data file."""
    frames = sample_data.build()
    before = os.environ.get("FPL_DATA_FILE")
    _use(write_data_file(frames, tmp_path_factory.mktemp("data") / "fpl_serving.sqlite"))
    yield frames
    if before is None:
        os.environ.pop("FPL_DATA_FILE", None)
    else:
        os.environ["FPL_DATA_FILE"] = before
    st.cache_data.clear()
    st.cache_resource.clear()


def _gameweeks_in(range_label: str) -> list[int]:
    last_n = RANGES[range_label]
    played = list(range(1, PLAYED + 1))
    return played if last_n is None else played[-last_n:]


def _stats_in(league, range_label: str) -> pd.DataFrame:
    stats = league["player_stats"]
    return stats[stats["pg_gameweek"].isin(_gameweeks_in(range_label))]


def _per_90_bar(range_label: str) -> float:
    return max(len(_gameweeks_in(range_label)) * 90 * PER_90_MIN_SHARE, PER_90_MIN_MINUTES)


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------


def test_gameweek_status(league):
    status = team_data.get_gameweek_status()
    assert (status["current_gw"], status["next_gw"]) == (PLAYED, PLAYED + 1)
    expected = league["gameweeks"].set_index("gw_id").loc[PLAYED + 1, "gw_deadline_time"]
    assert status["next_deadline"] == expected


def test_team_fixtures_are_the_upcoming_ones_from_both_sides(league):
    fixtures = team_data.get_team_fixtures()
    upcoming = league["fixtures"][league["fixtures"]["f_gameweek"] > PLAYED]
    assert sorted(fixtures["gw"].unique()) == sorted(upcoming["f_gameweek"].unique())
    assert len(fixtures) == 2 * len(upcoming)  # every match appears once per team

    short = league["teams"].set_index("team_id")["team_short_name"]
    match = upcoming.iloc[0]
    home = fixtures[(fixtures["team_id"] == match["f_home_team"]) & (fixtures["gw"] == match["f_gameweek"])].iloc[0]
    assert (home["venue"], home["opponent"], home["difficulty"]) == (
        "H",
        short[match["f_away_team"]],
        match["f_home_diff"],
    )
    assert home["team_short_name"] == short[match["f_home_team"]]
    away = fixtures[(fixtures["team_id"] == match["f_away_team"]) & (fixtures["gw"] == match["f_gameweek"])].iloc[0]
    assert (away["venue"], away["opponent"], away["difficulty"]) == (
        "A",
        short[match["f_home_team"]],
        match["f_away_diff"],
    )


def test_latest_news_is_newest_first_and_limited(league):
    with_news = league["players"][league["players"]["p_news"] != ""]
    news = team_data.get_latest_news(limit=5)
    assert len(news) == min(5, len(with_news))
    assert news["date"].is_monotonic_decreasing
    newest = with_news.sort_values("p_news_date", ascending=False).iloc[0]
    assert (news.iloc[0]["player"], news.iloc[0]["news"]) == (newest["p_full_name"], newest["p_news"])


def test_season_totals_match_the_stats(league):
    totals = team_data.get_player_season_totals().set_index("p_id")
    assert len(totals) == len(league["players"])
    expected = league["player_stats"].groupby("pg_id")[["pg_points", "pg_goals", "pg_assists", "pg_defcons"]].sum()
    for player_id in (1, 42, 300):
        row = totals.loc[player_id]
        assert (row["points"], row["goals"], row["assists"], row["defcons"]) == tuple(expected.loc[player_id])
    xg = league["player_stats"].groupby("pg_id")["pg_xG"].sum()
    assert totals.loc[42, "xg"] == pytest.approx(xg.loc[42])
    team = league["teams"].set_index("team_id").loc[league["players"].set_index("p_id").loc[42, "p_team"]]
    assert totals.loc[42, "team_short_name"] == team["team_short_name"]


def test_top_rated_and_differentials(league):
    rating = league["player_rating"]
    top = player_stats.get_top_rated(per_position=5)
    assert len(top) == 20 and (top["position_rank"] <= 5).all()
    assert top[["p_position", "position_rank"]].apply(tuple, axis=1).is_monotonic_increasing
    best_keeper = rating[rating["p_position"] == 1].sort_values("xpts_horizon", ascending=False).iloc[0]
    assert top.iloc[0]["p_id"] == best_keeper["p_id"] and top.iloc[0]["rating"] == best_keeper["star"]
    price = league["players"].set_index("p_id").loc[best_keeper["p_id"], "p_price"]
    assert top.iloc[0]["xpts_per_million"] == pytest.approx(best_keeper["xpts_horizon"] / price)

    midfielders = player_stats.get_top_rated(position=3)
    assert len(midfielders) == (rating["p_position"] == 3).sum() and (midfielders["p_position"] == 3).all()

    merged = rating.merge(league["players"], on="p_id")
    eligible = merged[(merged["p_ownership"] <= 10) & (merged["xmins_next_gw"] >= 60)]
    differentials = player_stats.get_in_form_differentials(max_ownership=10.0, limit=12)
    assert len(differentials) == min(12, len(eligible))
    assert differentials["xpts_horizon"].tolist() == sorted(eligible["xpts_horizon"], reverse=True)[:12]
    assert (differentials["ownership"] <= 10).all()


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


def test_players_and_player_info(league):
    players = player_info.get_players()
    assert len(players) == len(league["players"]) and list(players.columns) == ["p_id", "p_full_name"]

    source = league["players"].set_index("p_id").loc[42]
    team = league["teams"].set_index("team_id").loc[source["p_team"]]
    info = player_info.get_player_info(42).iloc[0]
    assert (info["p_full_name"], info["team"], info["position"]) == (
        source["p_full_name"],
        team["team_name"],
        source["p_position_name"],
    )
    assert info["price"] == source["p_price"] and float(info["form"]) == float(source["p_form"])
    assert (info["primary_colour"], info["badge_file"]) == (team["team_primary_colour"], team["team_badge_file"])
    assert player_info.get_player_info(99_999).empty


def test_ids_taken_from_a_dataframe_can_be_used_as_parameters(league):
    # Selectors hand the queries NumPy integers.
    assert not player_info.get_player_info(np.int64(42)).empty


def test_next_five_fixtures(league):
    team_id = league["players"].set_index("p_id").loc[42, "p_team"]
    fixtures = league["fixtures"]
    short = league["teams"].set_index("team_id")["team_short_name"]
    next_five = player_info.get_next_5(42)
    assert next_five["gw"].tolist() == list(range(PLAYED + 1, PLAYED + 6))
    for _, row in next_five.iterrows():
        match = fixtures[
            (fixtures["f_gameweek"] == row["gw"])
            & ((fixtures["f_home_team"] == team_id) | (fixtures["f_away_team"] == team_id))
        ].iloc[0]
        at_home = match["f_home_team"] == team_id
        assert row["venue"] == ("H" if at_home else "A")
        assert row["opponent"] == short[match["f_away_team"] if at_home else match["f_home_team"]]
        assert row["difficulty"] == (match["f_home_diff"] if at_home else match["f_away_diff"])


@pytest.mark.parametrize("range_label", list(RANGES))
def test_player_stats_total_the_range(league, range_label):
    stats = _stats_in(league, range_label)
    mine = stats[stats["pg_id"] == 42]
    points = league["player_points"]
    my_points = points[(points["pg_id"] == 42) & points["pg_gameweek"].isin(_gameweeks_in(range_label))]

    row = player_stats.get_player_stats(42, range_label).iloc[0]
    assert "gameweeks" not in row.index
    for column, source in [("points", "pg_points"), ("minutes", "pg_minutes"), ("goals", "pg_goals"),
                           ("saves", "pg_saves"), ("defcons", "pg_defcons"), ("starts", "pg_starts")]:  # fmt: skip
        assert row[column] == mine[source].sum()
    assert row["minutes_not_played"] == len(mine) * 90 - mine["pg_minutes"].sum()
    assert row["xg"] == pytest.approx(mine["pg_xG"].sum()) and row["xga"] == pytest.approx(mine["pg_xGa"].sum())
    for column in ("pf_minutes", "pf_cs", "pf_goals", "pf_assists", "pf_yellow", "pf_defcon"):
        assert row[column] == my_points[column].sum()


def test_player_with_no_gameweeks_has_no_stats(league):
    assert player_stats.get_player_stats(99_999, "All gameweeks").empty
    assert player_stats.get_rank_metrics(99_999, "All gameweeks").empty
    assert player_stats.get_gameweek_points(99_999, "All gameweeks").empty


@pytest.mark.parametrize("range_label", list(RANGES))
def test_gameweek_points(league, range_label):
    mine = _stats_in(league, range_label)
    mine = mine[mine["pg_id"] == 42].sort_values("pg_gameweek")
    points = player_stats.get_gameweek_points(42, range_label)
    assert points["gameweek"].tolist() == mine["pg_gameweek"].tolist()
    assert points["points"].tolist() == mine["pg_points"].tolist()


@pytest.mark.parametrize("range_label", list(RANGES))
def test_best_stats_in_position(league, range_label):
    stats = _stats_in(league, range_label)
    position = league["players"].set_index("p_id")["p_position_name"]
    totals = stats[stats["pg_id"].map(position) == "Defender"].groupby("pg_id").sum(numeric_only=True)
    totals = totals[totals["pg_starts"] >= 1]
    over_bar = totals[totals["pg_minutes"] >= _per_90_bar(range_label)]

    best = player_stats.get_best_stats("Defender", range_label).iloc[0]
    assert best["max_points"] == totals["pg_points"].max()
    assert best["max_goals"] == totals["pg_goals"].max()
    assert best["max_cs"] == totals["pg_clean_sheets"].max()
    assert best["max_dcp90"] == pytest.approx(
        round((over_bar["pg_defcons"] * 90 / over_bar["pg_minutes"]).max(), 1), abs=0.051
    )


@pytest.mark.parametrize("range_label", list(RANGES))
def test_ranks_within_position(league, range_label):
    players = league["players"].set_index("p_id")
    totals = _stats_in(league, range_label).groupby("pg_id").sum(numeric_only=True)
    totals["position"] = players["p_position"]
    totals["name"] = players["p_full_name"]
    # Form is text in the warehouse; ranking has to treat it as a number ("10.2" beats "9.8").
    totals["form"] = players["p_form"].astype(float)
    totals["dcp90"] = totals["pg_defcons"] * 90 / totals["pg_minutes"].where(totals["pg_minutes"] > 0)
    totals["qualified"] = totals["pg_minutes"] >= _per_90_bar(range_label)

    def rank(frame, column):
        ordered = frame.sort_values([column, "form", "name"], ascending=[False, False, True], kind="stable")
        return {player_id: i for i, player_id in enumerate(ordered.index, start=1)}

    for player_id in (3, 42, 120, 300):
        same_position = totals[totals["position"] == totals.loc[player_id, "position"]]
        row = player_stats.get_rank_metrics(player_id, range_label).iloc[0]
        assert row["points_rank"] == rank(same_position, "pg_points")[player_id]
        assert row["goals_rank"] == rank(same_position, "pg_goals")[player_id]
        assert row["cs_rank"] == rank(same_position, "pg_clean_sheets")[player_id]
        form_order = same_position.sort_values(
            ["form", "pg_points", "name"], ascending=[False, False, True], kind="stable"
        )
        assert row["form_rank"] == list(form_order.index).index(player_id) + 1
        if totals.loc[player_id, "qualified"]:
            assert row["dcp90_rank"] == rank(same_position[same_position["qualified"]], "dcp90")[player_id]
        else:
            # Under the minutes bar: no per-90 rank at all.
            assert pd.isna(row["dcp90_rank"]) and pd.isna(row["saves_rank"]) and pd.isna(row["pp90_rank"])


def test_rating(league):
    source = league["player_rating"].set_index("p_id").loc[42]
    star = player_stats.get_star(42).iloc[0]
    assert (star["player"], star["star"], star["xpts_horizon"]) == (
        source["player"],
        source["star"],
        source["xpts_horizon"],
    )
    assert player_stats.get_star(99_999).empty


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


def test_teams_and_profile(league):
    teams = team_results.get_teams()
    assert teams["team_name"].tolist() == sorted(league["teams"]["team_name"])
    source = league["teams"].set_index("team_id").loc[5]
    profile = team_results.get_team_profile(5).iloc[0]
    assert (profile["team_name"], profile["team_short_name"], profile["team_table_position"]) == (
        source["team_name"],
        source["team_short_name"],
        source["team_table_position"],
    )
    assert profile["badge_file"] == source["team_badge_file"]


@pytest.mark.parametrize("range_label", list(RANGES))
def test_team_results_and_ranks(league, range_label):
    results = league["team_fixture_results"]
    in_range = results[results["gw_id"].isin(_gameweeks_in(range_label))]
    mine = in_range[in_range["team_id"] == 5].sort_values("gw_id", ascending=False)

    shown = team_results.get_team_results(5, range_label)
    assert shown["gw_id"].tolist() == mine["gw_id"].tolist()
    assert shown["result"].tolist() == mine["result"].tolist()
    short = league["teams"].set_index("team_id")["team_short_name"]
    assert shown["opponent"].tolist() == [short[team] for team in mine["opponent_id"]]

    totals = in_range.groupby("team_id").agg(
        goals_scored=("own_score", "sum"), goals_conceded=("opp_score", "sum"), xg=("team_xg", "sum")
    )
    row = team_results.get_team_rank_metrics(5, range_label).iloc[0]
    assert row["games_played"] == len(mine)
    assert (row["wins"], row["draws"], row["losses"]) == tuple((mine["result"] == r).sum() for r in "WDL")
    assert row["goals_scored"] == totals.loc[5, "goals_scored"]
    assert row["clean_sheets"] == (mine["opp_score"] == 0).sum()
    assert row["total_xg"] == pytest.approx(totals.loc[5, "xg"])
    # Ties get distinct ranks, so check the rank is one of the positions sharing that total.
    scored = totals["goals_scored"]
    assert (scored > scored[5]).sum() + 1 <= row["goals_scored_rank"] <= (scored >= scored[5]).sum()
    assert row["xg_rank"] == (totals["xg"] > totals.loc[5, "xg"]).sum() + 1


def test_team_contributors(league):
    team_players = league["players"][league["players"]["p_team"] == 5]
    stats = league["player_stats"]
    expected = stats[stats["pg_id"].isin(team_players["p_id"]) & ((stats["pg_goals"] > 0) | (stats["pg_assists"] > 0))]
    contributors = team_results.get_team_contributors(5, "All gameweeks")
    assert len(contributors) == len(expected)
    assert contributors["gw_id"].is_monotonic_decreasing
    assert contributors["goals"].sum() == expected["pg_goals"].sum()


# ---------------------------------------------------------------------------
# My Team
# ---------------------------------------------------------------------------


def test_saved_managers_and_profile(league):
    known = manager_data.get_known_managers()
    assert known["m_team_name"].tolist() == sorted(league["manager_profile"]["m_team_name"])
    profile = manager_data.get_manager_profile(MANAGER_ID).iloc[0]
    assert (profile["m_team_name"], profile["m_overall_points"]) == ("Pep Talk FC", 412)
    # Stored as UTC text; the page parses it.
    loaded = pd.to_datetime(profile["m_loaded_at"], utc=True)
    assert loaded == league["manager_profile"]["m_loaded_at"].iloc[0].tz_localize("UTC")
    assert manager_data.get_manager_profile(1).empty


def test_squad_has_points_ratings_and_kick_off_status(league):
    squad = manager_data.get_manager_squad(MANAGER_ID)
    source = league["manager_squad"][league["manager_squad"]["m_id"] == MANAGER_ID]
    assert squad["squad_position"].tolist() == list(range(1, 16))
    assert squad["p_id"].tolist() == source.sort_values("squad_position")["p_id"].tolist()
    assert squad["is_starting"].sum() == 11 and squad["is_captain"].sum() == 1
    assert squad.loc[squad["is_captain"] == 1, "multiplier"].item() == 2

    stats = league["player_stats"]
    first = squad.iloc[0]
    points = stats[(stats["pg_id"] == first["p_id"]) & (stats["pg_gameweek"] == PLAYED)]["pg_points"].item()
    assert first["gw_points"] == points
    assert first["star"] == league["player_rating"].set_index("p_id").loc[first["p_id"], "star"]
    # Every team had one fixture in the gameweek, and it has kicked off.
    assert (squad["gw_fixtures"] == 1).all() and (squad["gw_kicked_off"] == 1).all()


def test_history_transfers_and_expected_points(league):
    history = manager_data.get_manager_gameweek_history(MANAGER_ID)
    assert history["gw_id"].tolist() == list(range(PLAYED, 0, -1))

    source = league["manager_transfers"][league["manager_transfers"]["m_id"] == MANAGER_ID]
    transfers = manager_data.get_manager_transfers(MANAGER_ID, limit=10)
    assert len(transfers) == 10 < len(source)
    assert transfers["transfer_time"].is_monotonic_decreasing
    assert transfers.iloc[0]["player_in"] == source.sort_values("transfer_time").iloc[-1]["player_in"]

    expected = manager_data.get_gameweek_expected(PLAYED)
    assert len(expected) == len(league["players"])
    assert expected.dtypes.astype(str).to_dict() == {"p_id": "int64", "gw_xpts": "float64"}


def test_managers_not_in_the_file_are_read_from_the_warehouse(league, monkeypatch):
    asked = []

    def warehouse(query, params=None):
        asked.append(params)
        return pd.DataFrame({"m_id": [params["entry_id"]], "transfer_time": ["2026-10-01"]})

    monkeypatch.setattr(manager_data, "run_live_query", warehouse)
    assert manager_data.get_manager_profile(555, live=True)["m_id"].tolist() == [555]
    assert not manager_data.get_manager_squad(555, live=True).empty
    assert not manager_data.get_manager_gameweek_history(555, live=True).empty
    assert not manager_data.get_manager_transfers(555, live=True).empty
    assert asked == [{"entry_id": 555}] * 4
    # ...and without live=True the same manager isn't found in the file.
    assert manager_data.get_manager_profile(555).empty


def test_warehouse_and_file_give_the_same_answers(league, tmp_path, monkeypatch):
    """The manager queries are written to run on both. Here the "warehouse"
    is a second copy of the tables behind a SQLAlchemy engine, which is how
    the real one is reached."""
    sqlalchemy = pytest.importorskip("sqlalchemy")
    copy = write_data_file(league, tmp_path / "warehouse.sqlite")
    engine = sqlalchemy.create_engine("sqlite://")

    @sqlalchemy.event.listens_for(engine, "connect")
    def attach(dbapi_connection, _record):
        dbapi_connection.execute(f"attach database '{copy}' as analytics")

    monkeypatch.setattr(database, "get_engine", lambda: engine)
    other = sample_data.OTHER_MANAGER_ID
    for query in (
        manager_data.get_manager_profile,
        manager_data.get_manager_squad,
        manager_data.get_manager_gameweek_history,
        manager_data.get_manager_transfers,
    ):
        from_file, from_warehouse = query(other), query(other, live=True)
        assert not from_warehouse.empty
        pd.testing.assert_frame_equal(from_warehouse, from_file)


# ---------------------------------------------------------------------------
# The data file changing underneath
# ---------------------------------------------------------------------------


def test_new_data_file_replaces_cached_results(league, tmp_path):
    frames = dict(league)
    path = write_data_file(frames, tmp_path / "fpl_serving.sqlite")
    previous = os.environ["FPL_DATA_FILE"]
    _use(path)
    try:
        assert manager_data.get_manager_profile(MANAGER_ID).iloc[0]["m_overall_points"] == 412
        assert not manager_data.get_gameweek_expected(PLAYED).empty

        # The pipeline runs again: new points, and (as with an older file) no expected-points table.
        frames["manager_profile"] = frames["manager_profile"].assign(m_overall_points=500)
        del frames["player_gameweek_expected"]
        write_data_file(frames, path)
        assert manager_data.get_manager_profile(MANAGER_ID).iloc[0]["m_overall_points"] == 412  # still cached

        database.current_data()  # every page run starts with this, and it notices the new file
        assert manager_data.get_manager_profile(MANAGER_ID).iloc[0]["m_overall_points"] == 500
        expected = manager_data.get_gameweek_expected(PLAYED)
        assert expected.empty and list(expected.columns) == ["p_id", "gw_xpts"]
    finally:
        _use(previous)


def test_no_data_file_is_reported_not_swallowed(league, tmp_path):
    previous = os.environ["FPL_DATA_FILE"]
    _use(tmp_path / "missing.sqlite")
    try:
        with pytest.raises(database.DataUnavailable, match="export_data.py"):
            database.current_data()
    finally:
        _use(previous)
