"""Database connectivity for the extraction pipeline.

A single engine factory is used everywhere the pipeline needs to talk
to SQL Server, so connection details live in exactly one place instead
of being duplicated (and drifting) across scripts.
"""
from __future__ import annotations

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

load_dotenv()

ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
DATABASE_NAME = "FPL"


def build_connection_string() -> str:
    """Assemble the ODBC connection string from environment variables.

    Reads FPL_DB_SERVER (defaults to "localhost"), FPL_DB_USER and
    FPL_DB_PASSWORD -- typically supplied via a local .env file (see
    .env.example) or, when running in Airflow, the container's
    environment.
    """
    server = os.getenv("FPL_DB_SERVER", "localhost")
    user = os.getenv("FPL_DB_USER")
    password = os.getenv("FPL_DB_PASSWORD")

    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server};"
        f"DATABASE={DATABASE_NAME};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )


def get_engine() -> Engine:
    """Create a SQLAlchemy engine for the FPL SQL Server database."""
    connection_string = build_connection_string()
    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}"
    )
