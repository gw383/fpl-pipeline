"""Tests for the pure SQL-string-building helper in
StreamLit/queries/player_stats.py.

Note: importing queries.player_stats pulls in streamlit and the
database module (SQLAlchemy/pyodbc), since query functions and the SQL
builder share one file. Those are real runtime dependencies of the
project (see requirements.txt) -- this test just checks the *shape* of
the generated SQL string, no actual database connection is made or
required to run it.
"""
from queries.player_stats import _range_filter_sql


class TestRangeFilterSql:
    def test_all_gameweeks_short_circuits_true(self):
        sql = _range_filter_sql("All gameweeks")
        assert "'All gameweeks' = 'All gameweeks'" in sql

    def test_last_10_gameweeks_uses_top_10(self):
        sql = _range_filter_sql("Last 10 gameweeks")
        assert "top (10)" in sql
        assert "'Last 10 gameweeks' = 'Last 10 gameweeks'" in sql

    def test_last_5_gameweeks_uses_top_5(self):
        sql = _range_filter_sql("Last 5 gameweeks")
        assert "top (5)" in sql

    def test_custom_gameweek_column_is_substituted(self):
        sql = _range_filter_sql("All gameweeks", gw_column="pg_gameweek")
        assert "pg_gameweek in (" in sql

    def test_default_gameweek_column_is_gw_id(self):
        sql = _range_filter_sql("All gameweeks")
        assert "gw_id in (" in sql

    def test_result_is_a_single_parenthesised_boolean_expression(self):
        sql = _range_filter_sql("Last 5 gameweeks").strip()
        assert sql.startswith("(")
        assert sql.endswith(")")
