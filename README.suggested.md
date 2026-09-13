# Fantasy Premier League Data Pipeline

An end-to-end data engineering pipeline for ingesting, transforming and modelling Fantasy Premier League data ready for analytics.

This project takes data from the Fantasy Premier League API and turns it into a structured data mart using Python, SQL Server, Apache Airflow, dbt and Docker, with Streamlit used as the reporting layer.

I built this project to explore the challenges involved in a typical data engineering pipeline, while developing my understanding of data ingestion, transformation, orchestration and overall pipeline architecture.

I also wanted to build something around a dataset that I have a genuine interest in, giving me a familiar "business problem" to work with while allowing me to focus on developing my analytical and engineering skills.



## Architecture


![Architecture](https://raw.githubusercontent.com/gw383/fpl-pipeline/main/docs/architecture.png "Architecture")




The transformed data is organised into a dimensional data model, with

fact and dimension tables designed around the requirements of the

reporting layer.


![Data Model](https://raw.githubusercontent.com/gw383/fpl-pipeline/main/docs/dbdiagram.png "dbmodel")




## Tech Stack

|Technology|Purpose|
|-|-|
|**Python**|Data ingestion and API interaction|
|**SQL Server**|Raw data storage and data warehouse|
|**Apache Airflow**|End-to-end pipeline orchestration|
|**dbt**|Data transformation and modelling|
|**Docker**|Containerisation of Airflow|
|**Streamlit**|Reporting and data visualisation|
|**pytest**|Automated testing of the Python codebase|
|**Git / GitHub**|Version control|



## Getting started

Everything the project needs is pinned in `requirements.txt` (and
`requirements-dev.txt` for testing). Copy `.env.example` to `.env` and
`airflow/.env.example` to `airflow/.env`, fill in your own database
credentials, then:

```
pip install -r requirements.txt -r requirements-dev.txt
cd transformation && dbt deps && dbt seed && dbt build
```

From there, `app.py` / `run_pipeline.py` (packaged as
`FPL Dashboard.exe` and `run_pipeline.exe` for day-to-day use) launch the
dashboard and trigger the Airflow pipeline respectively, without needing
a terminal open.



## Data quality

dbt tests are used to validate the transformed data before it is

made available to the reporting layer.

Examples:

\- Uniqueness

\- Not-null constraints

\- Referential integrity

\- Accepted values

\- Composite-key uniqueness (via the `dbt_utils` package) on the
  incremental fact models described below

The Python side of the codebase has its own automated test suite
(`pytest`), covering the shared ingestion helpers, the query-generation
logic behind the dashboard, and the small pure-Python utilities the
Player page depends on -- so regressions in those get caught before they
ever reach a dashboard user.



## Orchestration

Apache Airflow is responsible for orchestrating the end-to-end pipeline,

managing task dependencies, scheduling and data quality checks.


The DAG coordinates:

Python ingestion → dbt deps → dbt build → dbt tests

![dag](https://raw.githubusercontent.com/gw383/fpl-pipeline/main/docs/dag.png "dag")



## Transformation

dbt is used to transform the raw FPL data into a dimensional data mart.

Raw → Staging → Analytics

The analytics layer now includes two dedicated fact models,
`player_points` (per-player, per-gameweek fantasy points, broken down by
scoring category) and `player_rating` (the recommendation "star" score),
so the scoring rules live in one tested place in dbt instead of being
recomputed independently by every dashboard query that needed them.
`player_points` is built incrementally: once a gameweek is more than 10
days old it's treated as final and is never reprocessed on subsequent
runs, which keeps `dbt build` fast as a season accumulates gameweeks.

Reference data that isn't sourced from the FPL API -- currently the
season date ranges used to scope "current season" everywhere -- is
tracked as a version-controlled dbt seed (`transformation/seeds/`)
rather than living only in the warehouse, so it's reviewable and
reproducible the same way the rest of the transformation layer is.



## Operationalisation

A small desktop launcher is included to start the Docker environment

and trigger the Airflow pipeline. This could also be adapted to automatically

run at the end of a gameweek. I have chosen not to do this as the project is just

for personal use at the moment.

Ingestion is also incremental where the source data allows it: gameweeks
are only re-fetched from the FPL API while they're still provisional
(before the FPL API itself marks their stats as finalised), instead of
every gameweek being reloaded on every run regardless of whether
anything about it could have changed.



## Engineering challenges

Building the pipeline presented several challenges that required changes

to the architecture and implementation:

\- **Docker → SQL Server connectivity** — Airflow runs inside Docker while SQL Server runs on the host machine, requiring environment-specific database connectivity.

\- **Pipeline orchestration** — ingestion, transformation and testing

&#x20; needed to be coordinated through a single repeatable workflow.

\- **Data modelling** — the raw API data needed to be transformed into

&#x20; a dimensional model with clearly defined fact and dimension grains.

\- **Environment configuration** — database credentials and connection

&#x20; details needed to be separated from the application code while

&#x20; supporting both local and containerised execution.

\- **Changing FPL data** — fixtures, gameweeks and player data change

&#x20; throughout a season, requiring the pipeline to accommodate ongoing

&#x20; ingestion and transformation.

\- **Query duplication** — several dashboard pages independently
  recomputed the same fantasy-points and rating logic in Python-generated
  SQL, which had already started to drift out of sync between pages.
  Moving that logic into the two dbt models above (and dashboard-side
  caching via `st.cache_data`) keeps one implementation, tested once,
  reused everywhere.



## Reporting

Streamlit provides the reporting layer, consuming the transformed data

mart to provide an interface for exploring the FPL data.

Query results are cached (`st.cache_data`) so switching between filters
or revisiting a page you've already loaded doesn't re-hit the database
for data that hasn't changed, and a database or model issue now shows a
readable error message in the app instead of an unhandled traceback.



## Future Improvements

\- Cloud-hosted database

\- CI/CD for dbt testing and deployment

\- Automated monitoring and alerting

\- Automated pipeline execution

\- Develop manager and transfer data
