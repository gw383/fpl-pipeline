"""Airflow DAG: orchestrates the daily FPL ingest -> dbt build -> dbt test run.

Four tasks, run strictly in sequence:

1. ``ingest``    -- runs the Python extraction scripts (extraction/ingest.py),
                    pulling fresh data from the FPL API into raw.* tables.
2. ``dbt_deps``  -- runs `dbt deps`, installing the dbt packages declared in
                    transformation/packages.yml (currently dbt_utils) into
                    transformation/dbt_packages/. transformation/ is only
                    volume-mounted into the container at runtime, so this
                    can't be baked into the image at build time -- it has to
                    run here, before anything that compiles a model using a
                    package macro.
3. ``dbt_build`` -- runs `dbt build`, rebuilding every staging/analytics model.
4. ``dbt_test``  -- runs `dbt test`, validating the freshly-built models
                    before the reporting layer reads them.
"""
from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

with DAG(
    dag_id="fpl_pipeline",
    start_date=datetime(2026, 8, 1),
    schedule="0 6 * * *",
    catchup=False,
    tags=["fpl", "production"],
) as dag:

    ingest = BashOperator(
        task_id="ingest",
        bash_command=(
            "cd /opt/airflow/fpl-pipeline "
            "&& python extraction/ingest.py"
        ),
    )

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=(
            "cd /opt/airflow/fpl-pipeline/transformation "
            "&& dbt deps"
        ),
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            "cd /opt/airflow/fpl-pipeline/transformation "
            "&& dbt build"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            "cd /opt/airflow/fpl-pipeline/transformation "
            "&& dbt test"
        ),
    )

    ingest >> dbt_deps >> dbt_build >> dbt_test
