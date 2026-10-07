"""Run the whole pipeline in order: extraction -> dbt -> projection model ->
the dashboard's data file.

    python run_pipeline.py              # ...and write the data file locally
    python run_pipeline.py --publish    # ...and publish it for the hosted dashboard
    python run_pipeline.py --env dev    # the same, against the dev database

The same command works on your PC (against a local SQL Server or the cloud
database -- whatever ``.env`` points at) and in the scheduled GitHub
Actions job that keeps the hosted dashboard up to date. It waits for the
database to wake up first (an Azure SQL free-tier database pauses when
idle), and stops at the first step that fails.

The last step (``serving/export_data.py``) copies the analytics tables the
dashboard reads into one SQLite file, which is what the dashboard queries.

There are two environments, live and dev (``extraction/environment.py``):
each has its own database and its own published data file, so a change can
be run end to end in dev without the live site seeing it. ``--env`` picks
one (or set ``FPL_ENV``). On the ``main`` branch the default is live; on any
other branch you have to say which, so work in progress can't update the
live data by accident.

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


def current_branch(root: Path = ROOT) -> str | None:
    """The git branch checked out, or None if that can't be told (no git, not
    a checkout, a detached HEAD)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    branch = result.stdout.strip()
    return branch if result.returncode == 0 and branch and branch != "HEAD" else None


def resolve_environment(flag: str | None, environ: dict[str, str], branch: str | None) -> str:
    """Which environment this run updates: ``--env``, else ``FPL_ENV``, else
    live -- but only on the main branch (or where the branch isn't known).
    Anywhere else the choice has to be made explicitly."""
    from environment import LIVE, current

    if flag:
        return flag
    if environ.get("FPL_ENV"):
        return current(environ)
    if branch in (None, "main", "master"):
        return LIVE
    raise SystemExit(
        f"You're on the '{branch}' branch, so say which data this run should update:\n"
        "  python run_pipeline.py --env dev     the dev database and the dev site's data\n"
        "  python run_pipeline.py --env live    the live database and the live site's data\n"
        "(Setting FPL_ENV in .env makes one of them the default.)"
    )


def check_dbt_follows(environment: str, environ: dict[str, str]) -> None:
    """dbt only follows FPL_ENV through the project's own profile, which is
    used with a SQL login. With Windows authentication your ~/.dbt profile
    is in charge and would build into its own (live) database."""
    if environment != "live" and not environ.get("FPL_DB_USER") and not environ.get("DBT_PROFILES_DIR"):
        raise SystemExit(
            f"The {environment} environment needs a SQL login (FPL_DB_USER / FPL_DB_PASSWORD), so that dbt "
            "builds into the same database as the rest of the pipeline. With Windows authentication dbt uses "
            "your own ~/.dbt/profiles.yml, which doesn't know about environments."
        )


def export_command(python: str, publish: bool) -> list[str]:
    """The data-file step: export, and publish when asked."""
    return [python, "serving/export_data.py", *(["--publish"] if publish else [])]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the FPL pipeline: extract, dbt, model, data file.")
    parser.add_argument(
        "--publish", action="store_true", help="publish the data file for the hosted dashboard when done"
    )
    parser.add_argument(
        "--env", choices=["live", "dev"], help="which database and data file to update (default: FPL_ENV, else live)"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.path.insert(0, str(ROOT / "extraction"))
    sys.path.insert(0, str(ROOT / "serving"))
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from data_file import data_branch
    from db import DbSettings, get_engine, wait_until_ready

    try:
        environment = resolve_environment(args.env, dict(os.environ), current_branch())
        os.environ["FPL_ENV"] = environment  # every step below, and the settings read here, follow it
        settings = DbSettings.from_env()
    except ValueError as exc:  # FPL_ENV isn't live or dev, or dev is set to the live database
        raise SystemExit(str(exc)) from exc
    check_dbt_follows(environment, dict(os.environ))
    logger.info(
        "Environment: %s -> database %s on %s%s",
        environment,
        settings.database,
        settings.server,
        f", data file published to the '{data_branch(environment)}' branch" if args.publish else "",
    )
    logger.info("Connecting to the database...")
    wait_until_ready(get_engine(settings))

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
