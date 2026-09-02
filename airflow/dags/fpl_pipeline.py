from datetime import datetime

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator


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

    ingest >> dbt_build >> dbt_test
