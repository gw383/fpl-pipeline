"""Tests for the pure parsing helpers in the extraction scripts."""

from datetime import UTC, datetime

import pytest
from player_history import parse_history_past

from bootstrap_static import started_gameweeks
from config import parse_id_list
from managers import parse_picks
from pl_events import parse_match_goals, pl_season_id, previous_seasons

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


class TestStartedGameweeks:
    def test_only_gameweeks_past_their_deadline(self):
        events = [
            {"id": 1, "deadline_time": "2026-08-15T10:00:00Z"},
            {"id": 2, "deadline_time": "2026-09-28T11:59:00Z"},
            {"id": 3, "deadline_time": "2026-09-28T12:01:00Z"},
        ]
        assert started_gameweeks(events, now=NOW) == [1, 2]

    def test_sorted_and_ignores_missing_deadlines(self):
        events = [
            {"id": 5, "deadline_time": "2026-09-01T10:00:00Z"},
            {"id": 4, "deadline_time": "2026-08-25T10:00:00Z"},
            {"id": 6, "deadline_time": None},
        ]
        assert started_gameweeks(events, now=NOW) == [4, 5]


class TestParseIdList:
    def test_parses_and_strips(self):
        assert parse_id_list(" 123, 456 ,") == [123, 456]

    def test_empty_string_gives_empty_list(self):
        assert parse_id_list("") == []

    def test_rejects_non_integers(self):
        with pytest.raises(ValueError, match="comma-separated list of integers"):
            parse_id_list("123,abc")


class TestParsePicks:
    RESPONSE = {
        "active_chip": "bboost",
        "entry_history": {
            "points": 71,
            "total_points": 300,
            "overall_rank": 12345,
            "bank": 5,
            "value": 1003,
            "event_transfers": 2,
            "event_transfers_cost": 4,
            "points_on_bench": 9,
        },
        "picks": [
            {"element": 10, "position": 1, "multiplier": 2, "is_captain": True, "is_vice_captain": False},
            {"element": 20, "position": 12, "multiplier": 1, "is_captain": False, "is_vice_captain": False},
        ],
    }

    def test_picks_rows(self):
        picks, _ = parse_picks(194625, 5, self.RESPONSE)
        assert [(p["player_id"], p["position"], p["multiplier"]) for p in picks] == [(10, 1, 2), (20, 12, 1)]
        assert {p["entry_id"] for p in picks} == {194625}
        assert {p["event_id"] for p in picks} == {5}

    def test_history_row_includes_chip_and_hit(self):
        _, history = parse_picks(194625, 5, self.RESPONSE)
        assert history["points"] == 71
        assert history["event_transfers_cost"] == 4
        assert history["active_chip"] == "bboost"

    def test_missing_entry_history_gives_no_history_row(self):
        picks, history = parse_picks(1, 1, {"picks": [], "entry_history": None})
        assert picks == [] and history is None


class TestPremierLeagueGoals:
    MATCH = {"matchId": "2645195", "homeTeam": {"id": "3"}, "awayTeam": {"id": "9"}, "period": "FullTime"}
    EVENTS = {
        "homeTeam": {
            "goals": [
                {
                    "playerId": "223340",
                    "assistPlayerId": None,
                    "goalType": "Penalty",
                    "period": "SecondHalf",
                    "time": "97",
                },
                {
                    "playerId": "219847",
                    "assistPlayerId": "466075",
                    "goalType": "Goal",
                    "period": "FirstHalf",
                    "time": "15",
                },
            ]
        },
        "awayTeam": {"goals": []},
    }

    def test_one_row_per_goal_with_codes_and_type(self):
        rows = parse_match_goals(self.MATCH, self.EVENTS, matchweek=4)
        assert len(rows) == 2
        penalty = rows[0]
        assert penalty["goal_type"] == "Penalty" and penalty["player_code"] == 223340
        assert penalty["home_team_code"] == 3 and penalty["away_team_code"] == 9 and penalty["team_code"] == 3
        assert penalty["assist_code"] is None and rows[1]["assist_code"] == 466075
        assert {row["event_id"] for row in rows} == {4}

    def test_match_without_goals(self):
        assert parse_match_goals(self.MATCH, {"homeTeam": {"goals": None}, "awayTeam": {}}, 1) == []

    def test_season_id_is_the_starting_year(self):
        assert pl_season_id("2026-27") == 2026


class TestPlayerHistory:
    PLAYER = {"id": 533, "code": 204480, "team_join_date": "2026-07-01"}

    def test_one_row_per_past_season_with_numbers(self):
        summary = {
            "history_past": [
                {"season_name": "2024/25", "element_code": 204480, "minutes": 2500, "expected_goals": "1.20",
                 "bps": 480, "start_cost": 50, "end_cost": 52},
                {"season_name": "2025/26", "element_code": 204480, "minutes": 3000, "expected_goals": "2.05",
                 "defensive_contribution": 310, "tackles": "70"},
            ]
        }  # fmt: skip
        rows = parse_history_past(self.PLAYER, summary)
        assert [r["season_name"] for r in rows] == ["2024/25", "2025/26"]
        assert rows[1]["expected_goals"] == pytest.approx(2.05)
        assert rows[1]["tackles"] == pytest.approx(70.0)
        assert rows[0]["defensive_contribution"] is None  # not in older seasons
        assert all(r["player_id"] == 533 and r["team_join_date"] == "2026-07-01" for r in rows)

    def test_no_premier_league_history(self):
        assert parse_history_past(self.PLAYER, {"history_past": []}) == []
        assert parse_history_past(self.PLAYER, {}) == []

    def test_missing_element_code_falls_back_to_the_player(self):
        rows = parse_history_past(self.PLAYER, {"history_past": [{"season_name": "2025/26"}]})
        assert rows[0]["element_code"] == 204480


def test_previous_seasons():
    assert previous_seasons("2026-27", 2) == ["2025-26", "2024-25"]
    assert previous_seasons("2000-01", 1) == ["1999-00"]
