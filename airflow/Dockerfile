# Airflow image with dbt for SQL Server. The official image already ships the
# Microsoft ODBC driver and the Python libraries the extraction scripts use.
FROM apache/airflow:3.3.1

USER airflow

RUN pip install --no-cache-dir \
    dbt-core==1.9.8 \
    dbt-sqlserver==1.9.2 \
    python-dotenv==1.2.3
