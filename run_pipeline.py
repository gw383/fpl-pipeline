"""Run the whole pipeline in order: extraction -> dbt -> projection model ->
the dashboard's data file.

    python run_pipeline.py              # ...and write the data file locally
    python run_pipeline.py --publish    # ...and publish it for the hosted dashboard

The same command works on your PC (against a local SQL Server or the cloud
database -- whatever ``.env`` points at) and in the scheduled GitHub
Actions job that keeps the hosted dashboard up to date. It waits for the
database to wake up first (an Azure SQL free-tier database pauses when
idle), and stops at the first step that fails.

The last step (``serving/export_data.py``) copies the analytics tables the
dashboard reads into one SQLite file, which is what the dashboard queries.

dbt reads its connection from ``transformation/profiles/profiles.yml`` (the
same ``FPL_DB_*`` variables) when ``FPL_DB_USER`` is set; with Windows
authentication your own ``~/.dbt/profiles.yml`` is used as before.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger("run_pipeline")


def dbt_executable() -> str:
    """dbt from the same environment as this Python, else from PATH."""
    scripts = Path(sys.executable).parent
    for name in ("dbt.exe", "dbt"):
        if (scripts / name).exists():
            return str(scripts / name)
    found = shutil.which("dbt")
    if not found:
        raise SystemExit("dbt isn't installed in this environment (pip install -r requirements.txt).")
    return found


def dbt_environment(environ: dict[str, str]) -> dict[str, str]:
    """Environment for dbt: the project's env-driven profile when using a SQL
    login (unless DBT_PROFILES_DIR is already set)."""
    env = dict(environ)
    if env.get("FPL_DB_USER") and not env.get("DBT_PROFILES_DIR"):
        env["DBT_PROFILES_DIR"] = str(ROOT / "transformation" / "profiles")
    return env


def run(step: str, command: list[str], cwd: Path, env: dict[str, str]) -> None:
    logger.info("=== %s ===", step)
    result = subprocess.run(command, cwd=cwd, env=env)
    if result.returncode != 0:
        raise SystemExit(f"{step} failed (exit code {result.returncode}).")


def export_command(python: str, publish: bool) -> list[str]:
    """The data-file step: export, and publish when asked."""
    return [python, "serving/export_data.py", *(["--publish"] if publish else [])]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the FPL pipeline: extract, dbt, model, data file.")
    parser.add_argument(
        "--publish", action="store_true", help="publish the data file for the hosted dashboard when done"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.path.insert(0, str(ROOT / "extraction"))
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from db import get_engine, wait_until_ready

    logger.info("Connecting to the database...")
    wait_until_ready(get_engine())

    env = dict(os.environ)
    python = sys.executable
    run("Extract", [python, "extraction/ingest.py"], ROOT, env)
    dbt_env = dbt_environment(env)
    dbt = dbt_executable()
    run("dbt deps", [dbt, "deps"], ROOT / "transformation", dbt_env)
    run("dbt build", [dbt, "build"], ROOT / "transformation", dbt_env)
    run("Projection model", [python, "projections/run.py"], ROOT, env)
    run("Dashboard data file", export_command(python, args.publish), ROOT, env)
    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()
