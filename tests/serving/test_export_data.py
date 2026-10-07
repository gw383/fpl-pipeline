"""Tests for serving/export_data.py, with a SQLite database standing in for
the warehouse (its ``analytics`` schema is an attached database)."""

import json
import sqlite3

import pandas as pd
import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlalchemy.pool")

from data_file import OPTIONAL_TABLES, TABLES, connect, read_meta  # noqa: E402
from export_data import export, publish_requested, read_tables  # noqa: E402


def _warehouse(tmp_path, tables):
    """An engine whose ``analytics`` schema holds ``tables``."""
    source = tmp_path / "warehouse.sqlite"
    conn = sqlite3.connect(source)
    for i, table in enumerate(tables):
        pd.DataFrame({"id": [1, 2, 3][: i % 3 + 1], "Mixed_Case": 1.5}).to_sql(table, conn, index=False)
    conn.commit()
    conn.close()

    engine = sqlalchemy.create_engine("sqlite://")

    @sqlalchemy.event.listens_for(engine, "connect")
    def attach(dbapi_connection, _record):
        dbapi_connection.execute(f"attach database '{source}' as analytics")

    return engine


def test_reads_every_table_the_dashboard_needs(tmp_path):
    frames = read_tables(_warehouse(tmp_path, TABLES))
    assert list(frames) == list(TABLES)  # the optional table isn't there, and isn't required


def test_optional_tables_are_exported_when_present(tmp_path):
    frames = read_tables(_warehouse(tmp_path, [*TABLES, *OPTIONAL_TABLES]))
    assert set(frames) == set(TABLES) | set(OPTIONAL_TABLES)


def test_a_missing_required_table_stops_the_export(tmp_path):
    with pytest.raises(SystemExit, match=f"Couldn't read analytics.{TABLES[-1]}"):
        read_tables(_warehouse(tmp_path, TABLES[:-1]))


def test_export_writes_the_file_and_its_archive(tmp_path):
    file, archive = export(_warehouse(tmp_path, TABLES), tmp_path / "out" / "fpl_serving.sqlite")
    assert file.is_file() and archive == file.with_name("fpl_serving.sqlite.gz") and archive.is_file()
    assert set(json.loads(read_meta(file)["row_counts"])) == set(TABLES)
    conn = connect(file)
    try:
        # Column names are lower-cased on the way out.
        assert conn.execute("select mixed_case from analytics.players limit 1").fetchone() == (1.5,)
    finally:
        conn.close()


def test_export_is_stamped_with_its_environment(tmp_path):
    file, _ = export(_warehouse(tmp_path, TABLES), tmp_path / "fpl_serving.sqlite", "dev", "fpl_dev")
    meta = read_meta(file)
    assert (meta["environment"], meta["database"]) == ("dev", "fpl_dev")


@pytest.mark.parametrize(
    ("flag", "value", "expected"),
    [(True, "", True), (False, "1", True), (False, "TRUE", True), (False, "yes", True), (False, "0", False), (False, "", False)],
)  # fmt: skip
def test_publishing_is_opt_in(flag, value, expected):
    assert publish_requested(flag, {"FPL_PUBLISH_DATA": value}) is expected
