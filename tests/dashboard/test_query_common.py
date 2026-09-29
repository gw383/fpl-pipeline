"""Tests for dashboard/queries/common.py."""

import pytest

from queries.common import RANGE_OPTIONS, range_filter_sql


def test_all_gameweeks_is_a_no_op_predicate():
    assert range_filter_sql("All gameweeks") == "(1 = 1)"


@pytest.mark.parametrize(("label", "n"), [("Last 10 gameweeks", 10), ("Last 5 gameweeks", 5)])
def test_last_n_uses_top_n_played_gameweeks(label, n):
    sql = range_filter_sql(label, "ps.pg_gameweek")
    assert sql.startswith("(ps.pg_gameweek in (")
    assert f"top ({n})" in sql
    assert "gw_deadline_time < getdate()" in sql
    assert sql.count("(") == sql.count(")")


def test_every_option_is_supported():
    for label in RANGE_OPTIONS:
        range_filter_sql(label)


def test_unknown_range_is_rejected():
    with pytest.raises(ValueError, match="Unknown range"):
        range_filter_sql("Last 3 gameweeks")


@pytest.mark.parametrize("column", ["gw_id; drop table x", "1gw", "a.b.c", "gw id"])
def test_unsafe_column_names_are_rejected(column):
    with pytest.raises(ValueError, match="Invalid column"):
        range_filter_sql("All gameweeks", column)
