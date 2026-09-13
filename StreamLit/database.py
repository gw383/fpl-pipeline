"""Database connection for the Streamlit reporting layer.

Uses Windows-integrated authentication against the local SQL Server
instance, since the dashboard runs on the same machine as the
database. This is intentionally different from the extraction
pipeline's connection (extraction/db.py), which runs inside Docker and
authenticates with SQL Server credentials instead -- see the project
README for why the two entry points need different auth strategies.
"""
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=FPL;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={quote_plus(CONNECTION_STRING)}"
)


def run_query(query: str) -> pd.DataFrame:
    """Run `query` against `engine` and return the result.

    Every query function in queries/ goes through this instead of
    calling pd.read_sql directly, so a database problem (server not
    running, a model that hasn't been built yet, a typo'd column after
    a dbt change) shows the user a readable error banner instead of
    crashing the whole page with a raw SQLAlchemy traceback. On error,
    this returns an empty DataFrame so calling code's existing
    "no rows" handling (see Player.py, Home.py) takes over instead of a
    second exception.
    """
    try:
        return pd.read_sql(query, engine)
    except SQLAlchemyError as exc:
        st.error(f"Couldn't load data from the database: {exc}")
        return pd.DataFrame()
