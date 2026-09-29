"""Tests for extraction/managers.py: parsing, fetching (with the API faked)
and the per-manager refresh orchestration."""

import pytest
import requests

import managers
from managers import ManagerNotFound, fetch_manager, parse_manager_id, parse_profile, parse_transfers


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} error", response=response)


PROFILE = {
    "player_first_name": "George",
    "player_last_name": "Williams",
    "name": "Quantum of Tzolis",
    "summary_overall_points": 328,
    "summary_overall_rank": 2043461,
    "last_deadline_value": 1010,
    "last_deadline_bank": 0,
}
PICKS = {
    "active_chip": None,
    "entry_history": {"points": 45, "total_points": 328, "overall_rank": 2043461, "bank": 0, "value": 1010},
    "picks": [{"element": 10, "position": 1, "multiplier": 1, "is_captain": False, "is_vice_captain": False}],
}
TRANSFERS = [{"element_in": 1, "element_out": 2, "event": 5, "time": "2026-09-26T10:00:00Z"}]


def _fake_api(missing: set[str] = frozenset()):
    def fetch(path: str):
        if path in missing:
            raise _http_error(404)
        if path.endswith("/transfers"):
            return TRANSFERS
        if "/event/" in path:
            return PICKS
        return PROFILE

    return fetch


class TestParseManagerId:
    @pytest.mark.parametrize(("value", "expected"), [("194625", 194625), (" 42 ", 42), (7, 7)])
    def test_valid_ids(self, value, expected):
        assert parse_manager_id(value) == expected

    @pytest.mark.parametrize("value", ["", None, "abc", "-5", "0", "12.5", "1 2", "12345678901"])
    def test_invalid_ids(self, value):
        assert parse_manager_id(value) is None


class TestParsing:
    def test_profile_joins_first_and_last_name(self):
        row = parse_profile(1, PROFILE)
        assert row["player_name"] == "George Williams"
        assert row["team_name"] == "Quantum of Tzolis" and row["value"] == 1010

    def test_profile_without_name_is_none(self):
        assert parse_profile(1, {"name": "X"})["player_name"] is None

    def test_transfers(self):
        (row,) = parse_transfers(9, TRANSFERS)
        assert row["entry_id"] == 9 and row["element_in"] == 1 and row["event"] == 5


class TestFetchManager:
    def test_collects_every_dataset(self, monkeypatch):
        monkeypatch.setattr(managers, "fetch_json", _fake_api())
        manager = fetch_manager(123, [1, 2])
        assert len(manager.profile) == 1
        assert [row["event_id"] for row in manager.history] == [1, 2]
        assert len(manager.picks) == 2 and len(manager.transfers) == 1
        assert {row["entry_id"] for rows in manager.tables().values() for row in rows} == {123}

    def test_unknown_manager_raises(self, monkeypatch):
        monkeypatch.setattr(managers, "fetch_json", _fake_api(missing={"entry/999"}))
        with pytest.raises(ManagerNotFound):
            fetch_manager(999, [1])

    def test_other_http_errors_propagate(self, monkeypatch):
        def fetch(path):
            raise _http_error(503)

        monkeypatch.setattr(managers, "fetch_json", fetch)
        with pytest.raises(requests.HTTPError):
            fetch_manager(1, [1])

    def test_gameweek_without_picks_is_skipped(self, monkeypatch):
        # A team created after GW1's deadline has no GW1 picks.
        monkeypatch.setattr(managers, "fetch_json", _fake_api(missing={"entry/5/event/1/picks"}))
        manager = fetch_manager(5, [1, 2])
        assert [row["event_id"] for row in manager.history] == [2]


def test_ingest_managers_skips_failures_and_stores_the_rest(monkeypatch):
    stored = []

    def fake_fetch(entry_id, gameweeks):
        if entry_id == 2:
            raise ManagerNotFound("gone")
        return managers.ManagerData(entry_id)

    monkeypatch.setattr(managers, "fetch_manager", fake_fetch)
    monkeypatch.setattr(managers, "store_managers", lambda engine, fetched: stored.extend(m.entry_id for m in fetched))
    managers.ingest_managers(engine=None, entry_ids=[1, 2, 3], gameweeks=[1])
    assert stored == [1, 3]
