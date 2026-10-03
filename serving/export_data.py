"""Export the analytics tables the dashboard reads into its data file.

    python serving/export_data.py             # write serving/data/fpl_serving.sqlite (+ .gz)
    python serving/export_data.py --publish   # ...and publish it for the hosted dashboard

Runs as the last step of the pipeline (``run_pipeline.py``, the Airflow
DAG). The dashboard then answers every page from this file rather than
querying SQL Server, which is what keeps it fast: the warehouse only has to
be awake while the pipeline runs.

Setting ``FPL_PUBLISH_DATA=1`` publishes without the flag (for schedulers
that can't pass arguments).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extraction"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_file import DEFAULT_FILE, OPTIONAL_TABLES, SCHEMA, TABLES, compress, write_data_file  # noqa: E402

logger = logging.getLogger("export_data")


def read_tables(engine: Engine) -> dict[str, pd.DataFrame]:
    """Every table the dashboard needs, read whole from the warehouse."""
    frames: dict[str, pd.DataFrame] = {}
    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = list(TABLES) + [t for t in OPTIONAL_TABLES if inspector.has_table(t, schema=SCHEMA)]
        for table in tables:
            try:
                frames[table] = pd.read_sql(text(f"select * from {SCHEMA}.{table}"), conn)
            except Exception as exc:
                raise SystemExit(
                    f"Couldn't read {SCHEMA}.{table} for the dashboard's data file. Has the pipeline "
                    f"(dbt build and the projection model) run against this database?\n{exc}"
                ) from exc
            logger.info("Read %s.%s: %d rows", SCHEMA, table, len(frames[table]))
    return frames


def export(engine: Engine, path: Path = DEFAULT_FILE) -> tuple[Path, Path]:
    """Write the data file and its gzipped copy; returns both paths."""
    file = write_data_file(read_tables(engine), path)
    archive = compress(file)
    logger.info(
        "Wrote %s (%.1f MB) and %s (%.1f MB)",
        file,
        file.stat().st_size / 1e6,
        archive.name,
        archive.stat().st_size / 1e6,
    )
    return file, archive


def publish_requested(flag: bool, environ: dict[str, str] | None = None) -> bool:
    value = (environ if environ is not None else os.environ).get("FPL_PUBLISH_DATA", "")
    return flag or value.strip().lower() in ("1", "true", "yes")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_FILE, help="where to write the data file")
    parser.add_argument("--publish", action="store_true", help="also publish it for the hosted dashboard")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from db import get_engine, wait_until_ready

    engine = get_engine()
    wait_until_ready(engine)
    _, archive = export(engine, args.output)

    if publish_requested(args.publish):
        from publish_data import publish

        publish(archive)


if __name__ == "__main__":
    main()
