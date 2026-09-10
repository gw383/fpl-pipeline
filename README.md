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
|**Git / GitHub**|Version control|









## Data quality



dbt tests are used to validate the transformed data before it is

made available to the reporting layer.



Examples:

\- Uniqueness

\- Not-null constraints

\- Referential integrity

\- Accepted values





## Orchestration



Apache Airflow is responsible for orchestrating the end-to-end pipeline,

managing task dependencies, scheduling and data quality checks.



The DAG coordinates:



Python ingestion

&#x20;           ↓

Raw SQL Server data

&#x20;           ↓

dbt build

&#x20;           ↓

dbt tests



## Transformation



dbt is used to transform the raw FPL data into a dimensional data mart.



Raw → Staging → Intermediate → Marts



## Operationalisation



A small desktop launcher is included to start the Docker environment

and trigger the Airflow pipeline. This could also be adapted to automatically

run at the end of a gameweek. I have chosen not to do this as the project is just

for personal use at the moment.



## Engineering challenges



Building the pipeline presented several challenges that required changes

to the architecture and implementation:



\- \*\*Docker and SQL Server connectivity\*\* — Airflow runs inside Docker

&#x20; while SQL Server runs on the host machine, requiring environment-specific

&#x20; database connectivity.



\- \*\*Pipeline orchestration\*\* — ingestion, transformation and testing

&#x20; needed to be coordinated through a single repeatable workflow.



\- \*\*Data modelling\*\* — the raw API data needed to be transformed into

&#x20; a dimensional model with clearly defined fact and dimension grains.



\- \*\*Environment configuration\*\* — database credentials and connection

&#x20; details needed to be separated from the application code while

&#x20; supporting both local and containerised execution.



\- \*\*Changing FPL data\*\* — fixtures, gameweeks and player data change

&#x20; throughout a season, requiring the pipeline to accommodate ongoing

&#x20; ingestion and transformation.





## Reporting



Streamlit provides the reporting layer, consuming the transformed data

mart to provide an interface for exploring the FPL data.



## Future Improvements



\- Cloud-hosted database

\- CI/CD for dbt testing and deployment

\- Incremental data loading

\- Automated monitoring and alerting

\- Automated pipeline execution

\- Develop manager and transfer data













