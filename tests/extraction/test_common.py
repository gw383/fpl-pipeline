"""Tests for extraction/common.py's pure helpers."""

import pandas as pd

from common import GRACE_GAMEWEEKS, _gameweeks_needing_fetch, convert_nested_to_json, new_columns, sql_type_for


class TestConvertNestedToJson:
    def test_dict_column_is_serialised(self):
        df = pd.DataFrame({"stats": [{"goals": 1}, {"goals": 2}]})
        assert convert_nested_to_json(df)["stats"].tolist() == ['{"goals": 1}', '{"goals": 2}']

    def test_list_column_is_serialised(self):
        df = pd.DataFrame({"history": [[1, 2, 3], [4, 5]]})
        assert convert_nested_to_json(df)["history"].tolist() == ["[1, 2, 3]", "[4, 5]"]

    def test_plain_columns_are_left_alone(self):
        df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        pd.testing.assert_frame_equal(convert_nested_to_json(df.copy()), df)

    def test_mixed_column_only_serialises_nested_values(self):
        df = pd.DataFrame({"mixed": [{"a": 1}, None, "plain"]})
        result = convert_nested_to_json(df)["mixed"].tolist()
        assert result[0] == '{"a": 1}' and pd.isna(result[1]) and result[2] == "plain"


class TestGameweeksNeedingFetch:
    def test_never_ingested_gameweek_is_fetched(self):
        assert _gameweeks_needing_fetch([1], ingested=set(), checked={1: True}) == [1]

    def test_unchecked_gameweek_is_refetched(self):
        assert _gameweeks_needing_fetch([1], ingested={1}, checked={1: False}) == [1]

    def test_gameweek_missing_from_checked_is_treated_as_unchecked(self):
        assert _gameweeks_needing_fetch([1], ingested={1}, checked={}) == [1]

    def test_settled_gameweeks_outside_grace_window_are_skipped(self):
        gameweeks = list(range(1, 11))
        result = _gameweeks_needing_fetch(gameweeks, ingested=set(gameweeks), checked=dict.fromkeys(gameweeks, True))
        assert result == gameweeks[-GRACE_GAMEWEEKS:]

    def test_recently_ingested_checked_gameweek_stays_in_grace_window(self):
        # The case behind the grace window: a gameweek captured mid-correction
        # and marked data_checked straight afterwards must still be re-fetched.
        assert _gameweeks_needing_fetch([1, 2, 3], ingested={1, 2, 3}, checked={1: True, 2: True, 3: True}) == [2, 3]

    def test_mixed_batch(self):
        gameweeks = [1, 2, 3, 4, 5, 6]
        ingested = {1, 2, 3, 4, 5}
        checked = {1: True, 2: False, 3: True, 4: True, 5: True}
        # 2 unchecked, 4-5 in grace window, 6 never ingested; 1 and 3 settled.
        assert _gameweeks_needing_fetch(gameweeks, ingested, checked) == [2, 4, 5, 6]

    def test_preserves_input_order(self):
        assert _gameweeks_needing_fetch([5, 1, 3], ingested=set(), checked={}) == [5, 1, 3]


class TestNewColumns:
    def test_fields_the_table_lacks_are_found_in_order(self):
        columns = ["id", "stats.minutes", "stats.can_auto_sub_out", "stats.can_auto_sub_in"]
        existing = {"id", "stats.minutes"}
        assert new_columns(columns, existing) == ["stats.can_auto_sub_out", "stats.can_auto_sub_in"]

    def test_names_are_compared_without_case(self):
        assert new_columns(["ID", "Season"], {"id", "season"}) == []

    def test_nothing_new(self):
        assert new_columns([], {"id"}) == []


class TestSqlTypeFor:
    def test_types_match_what_to_sql_creates(self):
        assert sql_type_for(pd.Series([True, False])) == "BIT"
        assert sql_type_for(pd.Series([1, 2])) == "BIGINT"
        assert sql_type_for(pd.Series([1.5, None])) == "FLOAT"
        assert sql_type_for(pd.Series(pd.to_datetime(["2026-11-26"]))) == "DATETIME2"
        assert sql_type_for(pd.Series(["0.36", "1.2"])) == "NVARCHAR(max)"
