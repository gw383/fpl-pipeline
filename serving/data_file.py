"""The dashboard's data file: every analytics table the dashboard reads, in
one SQLite database.

The pipeline writes it after each run (``serving/export_data.py``) and the
dashboard queries it instead of SQL Server, so a page view never waits on
the warehouse. Nothing here needs SQL Server, SQLAlchemy or Streamlit: this
module is shared by the exporter, the dashboard and the tests.

The file is attached under the name ``analytics``, so queries read
``analytics.players`` exactly as they would in the warehouse.
"""

from __future__ import annotations

import datetime as dt
import decimal
import gzip
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path

import pandas as pd

FILE_NAME = "fpl_serving.sqlite"
ARCHIVE_NAME = f"{FILE_NAME}.gz"
DATA_DIR = Path(__file__).resolve().parent / "data"  # git-ignored
DEFAULT_FILE = DATA_DIR / FILE_NAME

# The branch the archive is published to, and where the hosted dashboard
# downloads it from (see serving/publish_data.py).
DATA_BRANCH = "data"

SCHEMA = "analytics"
META_TABLE = "serving_meta"
# Bump when a change to the file means older dashboard code can't read it.
FORMAT_VERSION = 1

# analytics tables the dashboard reads. The export fails if one is missing.
TABLES = (
    "gameweeks",
    "fixtures",
    "teams",
    "players",
    "player_stats",
    "player_points",
    "player_rating",
    "team_fixture_results",
    "manager_profile",
    "manager_squad",
    "manager_gameweek_history",
    "manager_transfers",
)
# Exported when present (written by newer versions of the projection run).
OPTIONAL_TABLES = ("player_gameweek_expected",)

# Lookup columns worth an index: (table, columns).
INDEXES = (
    ("players", ("p_id",)),
    ("players", ("p_team",)),
    ("player_stats", ("pg_id", "pg_gameweek")),
    ("player_stats", ("pg_gameweek",)),
    ("player_points", ("pg_id", "pg_gameweek")),
    ("player_rating", ("p_id",)),
    ("fixtures", ("f_gameweek",)),
    ("team_fixture_results", ("team_id",)),
    ("manager_profile", ("m_id",)),
    ("manager_squad", ("m_id",)),
    ("manager_gameweek_history", ("m_id",)),
    ("manager_transfers", ("m_id",)),
    ("player_gameweek_expected", ("gw",)),
)

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"  # what SQLite's datetime('now') returns, so the two compare


def _normalise_value(value):
    """One cell of an object column, as something SQLite stores natively."""
    if value is None or value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, dt.datetime):
        if value.tzinfo is not None:
            value = value.astimezone(dt.UTC).replace(tzinfo=None)
        return value.strftime(DATETIME_FORMAT)
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dt.time):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    return value


def normalise(frame: pd.DataFrame) -> pd.DataFrame:
    """``frame`` ready for SQLite: lower-case column names (the warehouse is
    case-insensitive, so queries may spell them either way), timestamps as
    UTC ``YYYY-MM-DD HH:MM:SS`` text, decimals as floats and booleans as 0/1."""
    out = pd.DataFrame(index=frame.index)
    for name in frame.columns:
        column = frame[name]
        if pd.api.types.is_datetime64_any_dtype(column):
            if getattr(column.dt, "tz", None) is not None:
                column = column.dt.tz_convert("UTC").dt.tz_localize(None)
            text = column.dt.strftime(DATETIME_FORMAT).astype(object)
            column = text.where(column.notna(), None)
        elif pd.api.types.is_bool_dtype(column):
            column = column.astype(object).map(_normalise_value)
        elif pd.api.types.is_numeric_dtype(column):
            if pd.api.types.is_extension_array_dtype(column) and column.isna().any():
                column = column.astype("float64")  # nullable integers: missing becomes NULL
        else:
            column = column.astype(object).map(_normalise_value)
        out[str(name).lower()] = column
    return out


def write_data_file(
    frames: dict[str, pd.DataFrame], path: Path = DEFAULT_FILE, exported_at: dt.datetime | None = None
) -> Path:
    """Write ``frames`` (table name -> rows) as the data file at ``path``.

    It is built next to ``path`` and moved into place at the end, so a
    dashboard reading the old file never sees a half-written one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    building = path.with_name(f"{path.name}.building")
    building.unlink(missing_ok=True)
    exported_at = (exported_at or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)

    conn = sqlite3.connect(building)
    try:
        counts, written_columns = {}, {}
        for table, frame in frames.items():
            normalised = normalise(frame)
            normalised.to_sql(table, conn, index=False, if_exists="replace", chunksize=5000)
            counts[table] = len(normalised)
            written_columns[table] = set(normalised.columns)
        for table, columns in INDEXES:
            if set(columns) <= written_columns.get(table, set()):
                conn.execute(f"create index ix_{table}_{'_'.join(columns)} on {table} ({', '.join(columns)})")
        conn.execute(f"create table {META_TABLE} (key text primary key, value text)")
        conn.executemany(
            f"insert into {META_TABLE} (key, value) values (?, ?)",
            [
                ("format_version", str(FORMAT_VERSION)),
                ("exported_at", exported_at.strftime(DATETIME_FORMAT)),
                ("row_counts", json.dumps(counts)),
            ],
        )
        conn.commit()
        conn.execute("vacuum")
    finally:
        conn.close()

    _replace(building, path)
    return path


def _replace(source: Path, target: Path, attempts: int = 10) -> None:
    """Move ``source`` over ``target``. On Windows that fails while another
    process has the target open (a dashboard mid-query), so retry briefly."""
    for attempt in range(1, attempts + 1):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts:
                raise
            time.sleep(0.5)


def compress(path: Path = DEFAULT_FILE) -> Path:
    """Gzip ``path`` next to itself (``fpl_serving.sqlite.gz``), for publishing."""
    path = Path(path)
    archive = path.with_name(f"{path.name}.gz")
    with path.open("rb") as source, gzip.open(archive, "wb", compresslevel=6) as target:
        shutil.copyfileobj(source, target)
    return archive


def decompress(archive: bytes, target: Path) -> Path:
    """Write a downloaded archive's contents to ``target``."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    building = target.with_name(f"{target.name}.building")
    building.write_bytes(gzip.decompress(archive))
    _replace(building, target)
    return target


def connect(path: Path) -> sqlite3.Connection:
    """A read-only connection with the data file attached as ``analytics``."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(":memory:")
    conn.execute(f"attach database ? as {SCHEMA}", (str(path),))
    conn.execute("pragma query_only = on")
    return conn


def read_meta(path: Path) -> dict[str, str]:
    """The file's metadata (``exported_at``, ``format_version``, ``row_counts``).
    Raises ValueError if ``path`` isn't a data file."""
    try:
        conn = connect(path)
        try:
            rows = conn.execute(f"select key, value from {SCHEMA}.{META_TABLE}").fetchall()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"{path} isn't a dashboard data file: {exc}") from exc
    return dict(rows)


def exported_at(meta: dict[str, str]) -> dt.datetime | None:
    """When the file was exported (UTC), from its metadata."""
    value = meta.get("exported_at")
    if not value:
        return None
    try:
        return dt.datetime.strptime(value, DATETIME_FORMAT).replace(tzinfo=dt.UTC)
    except ValueError:
        return None


def has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        f"select count(*) from {SCHEMA}.sqlite_master where type = 'table' and name = ?", (table,)
    ).fetchone()
    return bool(row[0])
