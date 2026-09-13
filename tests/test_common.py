"""Tests for extraction/common.py's pure helpers.

convert_nested_to_json and _gameweeks_needing_fetch don't touch a
database or the network, so they're tested directly here -- no engine,
no requests_mock needed. determine_gameweeks_to_fetch itself (the
thin wrapper that actually queries SQL Server) is not covered here;
it's exercised end-to-end by running the pipeline against a real
database instead.
"""
import pandas as pd

from common import _gameweeks_needing_fetch, convert_nested_to_json


class TestConvertNestedToJson:
    def test_dict_column_is_serialised(self):
        df = pd.DataFrame({"stats": [{"goals": 1}, {"goals": 2}]})
        result = convert_nested_to_json(df)
        assert result["stats"].tolist() == ['{"goals": 1}', '{"goals": 2}']

    def test_list_column_is_serialised(self):
        df = pd.DataFrame({"history": [[1, 2, 3], [4, 5]]})
        result = convert_nested_to_json(df)
        assert result["history"].tolist() == ["[1, 2, 3]", "[4, 5]"]

    def test_plain_columns_are_left_alone(self):
        df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        result = convert_nested_to_json(df.copy())
        pd.testing.assert_frame_equal(result, df)

    def test_mixed_column_with_some_nested_values(self):
        # A column can have nested values on some rows and plain values
        # (or None) on others -- the FPL API does this in practice.
        df = pd.DataFrame({"mixed": [{"a": 1}, None, "plain"]})
        result = convert_nested_to_json(df)
        assert result["mixed"].tolist() == ['{"a": 1}', None, "plain"]


class TestGameweeksNeedingFetch:
    def test_never_ingested_gameweek_is_fetched(self):
        assert _gameweeks_needing_fetch([1], ingested=set(), checked={1: True}) == [1]

    def test_ingested_and_data_checked_gameweek_is_skipped(self):
        assert _gameweeks_needing_fetch([1], ingested={1}, checked={1: True}) == []

    def test_ingested_but_not_yet_data_checked_gameweek_is_refetched(self):
        assert _gameweeks_needing_fetch([1], ingested={1}, checked={1: False}) == [1]

    def test_ingested_gameweek_missing_from_checked_is_treated_as_unchecked(self):
        # No raw_gameweeks row at all for this gameweek/season -- err on
        # the side of an extra fetch rather than silently going stale.
        assert _gameweeks_needing_fetch([1], ingested={1}, checked={}) == [1]

    def test_mixed_batch_keeps_only_ones_needing_a_fetch(self):
        all_gameweeks = [1, 2, 3, 4]
        ingested = {1, 2, 3}
        checked = {1: True, 2: False, 3: True}
        # 1: ingested + checked -> skip
        # 2: ingested but not checked -> fetch
        # 3: ingested + checked -> skip
        # 4: never ingested -> fetch
        assert _gameweeks_needing_fetch(all_gameweeks, ingested, checked) == [2, 4]

    def test_preserves_input_order(self):
        assert _gameweeks_needing_fetch([5, 1, 3], ingested=set(), checked={}) == [5, 1, 3]
