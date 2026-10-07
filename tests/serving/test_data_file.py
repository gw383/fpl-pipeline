"""Tests for serving/data_file.py: writing and reading the dashboard's data file."""

import datetime as dt
import decimal
import json
import sqlite3

import pandas as pd
import pytest

from data_file import (
    DATA_DIR,
    FORMAT_VERSION,
    archive_meta,
    compress,
    connect,
    data_branch,
    decompress,
    default_file,
    environment_of,
    exported_at,
    has_table,
    normalise,
    read_meta,
    write_data_file,
)


def _frames():
    return {
        "players": pd.DataFrame({"p_id": [1, 2], "p_team": [10, 20], "p_full_name": ["Ann Lee", "Bo Diaz"]}),
        "gameweeks": pd.DataFrame(
            {"gw_id": [1, 2], "gw_deadline_time": pd.to_datetime(["2026-08-15 17:30:00", "2026-08-22 10:00:00"])}
        ),
    }


def test_normalise_makes_every_value_sqlite_native():
    frame = pd.DataFrame(
        {
            "pg_xG": [decimal.Decimal("0.25"), None],
            "When": pd.to_datetime(["2026-08-15 17:30:00", None]),
            "aware": pd.to_datetime(["2026-08-15 18:30:00+01:00", "2026-08-16 00:00:00+00:00"], utc=True),
            "flag": [True, False],
            "day": [dt.date(2026, 8, 15), None],
            "stamp": [dt.datetime(2026, 8, 15, 18, 30, tzinfo=dt.timezone(dt.timedelta(hours=1))), None],
            "name": ["Ann", None],
            "n": [1, 2],
        }
    )
    out = normalise(frame)
    # The warehouse is case-insensitive about column names; the file is lower-case throughout.
    assert list(out.columns) == ["pg_xg", "when", "aware", "flag", "day", "stamp", "name", "n"]
    assert out["pg_xg"][0] == 0.25 and isinstance(out["pg_xg"][0], float)  # was a Decimal
    assert out["when"][0] == "2026-08-15 17:30:00"
    assert out["aware"].tolist() == ["2026-08-15 17:30:00", "2026-08-16 00:00:00"]  # stored as UTC
    assert out["flag"].tolist() == [1, 0]
    assert out["day"][0] == "2026-08-15"
    assert out["stamp"][0] == "2026-08-15 17:30:00"
    assert out["name"][0] == "Ann"
    assert out["n"].tolist() == [1, 2]
    for column in ("pg_xg", "when", "day", "stamp", "name"):
        assert pd.isna(out[column][1])


def test_missing_values_are_stored_as_null(tmp_path):
    frame = pd.DataFrame(
        {
            "id": [1, 2],
            "score": [1.5, float("nan")],
            "amount": [decimal.Decimal("2.5"), None],
            "at": pd.to_datetime(["2026-08-15 17:30:00", None]),
            "name": ["Ann", None],
            "count": pd.array([3, pd.NA], dtype="Int64"),
            "label": pd.array(["x", pd.NA], dtype="string"),
        }
    )
    conn = connect(write_data_file({"t": frame}, tmp_path / "data.sqlite"))
    try:
        missing = conn.execute("select score, amount, at, name, count, label from analytics.t where id = 2")
        assert missing.fetchone() == (None,) * 6
        assert conn.execute("select count, label from analytics.t where id = 1").fetchone() == (3, "x")
        assert conn.execute("select typeof(amount), typeof(at) from analytics.t where id = 1").fetchone() == (
            "real",
            "text",
        )
    finally:
        conn.close()


def test_written_file_is_queried_as_the_analytics_schema(tmp_path):
    path = write_data_file(_frames(), tmp_path / "data.sqlite")
    conn = connect(path)
    try:
        rows = conn.execute("select p_full_name from analytics.players where p_id = :id", {"id": 2}).fetchall()
        assert rows == [("Bo Diaz",)]
        # Timestamps are text in the shape datetime('now') uses, so they compare with it.
        assert conn.execute("select gw_deadline_time from analytics.gameweeks where gw_id = 1").fetchone() == (
            "2026-08-15 17:30:00",
        )
        assert conn.execute("select count(*) from analytics.gameweeks where gw_deadline_time < datetime('now')")
        assert has_table(conn, "players") and not has_table(conn, "player_gameweek_expected")
        indexes = {row[0] for row in conn.execute("select name from analytics.sqlite_master where type = 'index'")}
        assert {"ix_players_p_id", "ix_players_p_team"} <= indexes
    finally:
        conn.close()


def test_connection_is_read_only(tmp_path):
    path = write_data_file(_frames(), tmp_path / "data.sqlite")
    conn = connect(path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("delete from analytics.players")
    finally:
        conn.close()


def test_metadata_records_when_and_what(tmp_path):
    when = dt.datetime(2026, 10, 3, 6, 21, 30, tzinfo=dt.UTC)
    path = write_data_file(_frames(), tmp_path / "data.sqlite", exported_at=when)
    meta = read_meta(path)
    assert int(meta["format_version"]) == FORMAT_VERSION
    assert exported_at(meta) == when
    assert json.loads(meta["row_counts"]) == {"players": 2, "gameweeks": 2}


def test_each_environment_has_its_own_file_and_branch():
    assert default_file() == DATA_DIR / "fpl_serving.sqlite" and data_branch() == "data"
    assert default_file("dev") == DATA_DIR / "dev" / "fpl_serving.sqlite" and data_branch("dev") == "data-dev"


def test_file_records_the_environment_and_database_it_came_from(tmp_path):
    path = write_data_file(_frames(), tmp_path / "data.sqlite", environment="dev", database="fpl_dev")
    meta = read_meta(path)
    assert (environment_of(meta), meta["database"]) == ("dev", "fpl_dev")
    assert archive_meta(compress(path)) == meta
    # Unless told otherwise a file is live, as are files written before environments existed.
    assert environment_of(read_meta(write_data_file(_frames(), tmp_path / "live.sqlite"))) == "live"
    assert environment_of({"format_version": "1"}) == "live"


def test_rewriting_replaces_the_file_and_leaves_nothing_behind(tmp_path):
    path = tmp_path / "nested" / "data.sqlite"
    write_data_file(_frames(), path)
    write_data_file({"players": _frames()["players"].head(1)}, path)
    assert json.loads(read_meta(path)["row_counts"]) == {"players": 1}
    assert [p.name for p in path.parent.iterdir()] == ["data.sqlite"]


def test_archive_round_trip(tmp_path):
    path = write_data_file(_frames(), tmp_path / "data.sqlite")
    archive = compress(path)
    assert archive.name == "data.sqlite.gz"
    copy = decompress(archive.read_bytes(), tmp_path / "copy" / "data.sqlite")
    assert copy.read_bytes() == path.read_bytes()


def test_a_file_that_is_not_a_data_file_is_rejected(tmp_path):
    not_sqlite = tmp_path / "junk.sqlite"
    not_sqlite.write_text("this is not a database")
    with pytest.raises(ValueError, match="isn't a dashboard data file"):
        read_meta(not_sqlite)

    other = tmp_path / "other.sqlite"
    conn = sqlite3.connect(other)
    conn.execute("create table t (x)")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="isn't a dashboard data file"):
        read_meta(other)

    with pytest.raises(FileNotFoundError):
        connect(tmp_path / "missing.sqlite")
