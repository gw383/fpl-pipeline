"""SQL Server access for the dashboard.

Connection settings come from the same environment variables as the
extraction pipeline (``FPL_DB_SERVER``, ``FPL_DB_NAME``, and optionally
``FPL_DB_USER`` / ``FPL_DB_PASSWORD``; without a user, Windows integrated
authentication is used).
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()


@st.cache_resource
def get_engine() -> Engine:
    """One pooled engine per Streamlit server process."""
    user = os.getenv("FPL_DB_USER")
    auth = f"UID={user};PWD={os.getenv('FPL_DB_PASSWORD', '')};" if user else "Trusted_Connection=yes;"
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={os.getenv('FPL_DB_SERVER', 'localhost')};"
        f"DATABASE={os.getenv('FPL_DB_NAME', 'FPL')};"
        f"{auth}"
        "TrustServerCertificate=yes;"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}")


def run_query(query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run a parameterised query (``:name`` placeholders) and return a DataFrame.

    Database errors are shown as a banner and an empty DataFrame is returned,
    so each page's own "no data" handling takes over instead of a traceback.
    """
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(text(query), conn, params=params or {})
    except SQLAlchemyError as exc:
        st.error(f"Couldn't load data from the database: {exc}")
        return pd.DataFrame()
