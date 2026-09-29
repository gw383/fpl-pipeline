"""Daily FPL pipeline: extract from the FPL API into SQL Server, build and test
the dbt project, then project every player's expected points.

    ingest  ->  dbt_deps  ->  dbt_build  ->  project

``dbt build`` runs seeds, models and tests in dependency order, so a failing
test stops the models downstream of it (and the projection) from running on
bad data. ``project`` writes analytics.player_rating, player_projection and
team_rating.
``max_active_runs=1`` stops a manual trigger overlapping the scheduled run.
"""

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

PROJECT_DIR = "/opt/airflow/fpl-pipeline"
DBT_DIR = f"{PROJECT_DIR}/transformation"

with DAG(
    dag_id="fpl_pipeline",
    description="FPL API -> SQL Server raw -> dbt staging/analytics -> expected-points projections",
    start_date=datetime(2026, 8, 1),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["fpl"],
) as dag:
    ingest = BashOperator(
        task_id="ingest",
        bash_command=f"cd {PROJECT_DIR} && python extraction/ingest.py",
    )

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"cd {DBT_DIR} && dbt deps",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {DBT_DIR} && dbt build",
    )

    project = BashOperator(
        task_id="project",
        bash_command=f"cd {PROJECT_DIR} && python projections/run.py",
    )

    ingest >> dbt_deps >> dbt_build >> project
