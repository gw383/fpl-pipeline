"""SQL Server connectivity for the extraction pipeline."""

from __future__ import annotations

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

load_dotenv()

ODBC_DRIVER = "ODBC Driver 18 for SQL Server"


def build_connection_string() -> str:
    """Assemble an ODBC connection string from environment variables.

    ``FPL_DB_SERVER`` (default ``localhost``) and ``FPL_DB_NAME`` (default
    ``FPL``) locate the database. If ``FPL_DB_USER`` is set, SQL Server
    authentication is used with ``FPL_DB_PASSWORD``; otherwise the connection
    falls back to Windows integrated authentication.
    """
    server = os.getenv("FPL_DB_SERVER", "localhost")
    database = os.getenv("FPL_DB_NAME", "FPL")
    user = os.getenv("FPL_DB_USER")

    auth = f"UID={user};PWD={os.getenv('FPL_DB_PASSWORD', '')};" if user else "Trusted_Connection=yes;"

    return f"DRIVER={{{ODBC_DRIVER}}};SERVER={server};DATABASE={database};{auth}TrustServerCertificate=yes;"


def get_engine() -> Engine:
    """Create a SQLAlchemy engine for the FPL database.

    ``fast_executemany`` makes pyodbc send each ``DataFrame.to_sql`` batch
    as a single round trip instead of one INSERT per row.
    """
    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={quote_plus(build_connection_string())}",
        fast_executemany=True,
    )
