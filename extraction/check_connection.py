"""Standalone diagnostic: verifies local SQL Server connectivity.

Run directly with `python check_connection.py` to sanity-check that
the SQL Server ODBC driver and instance are reachable before running
the full pipeline. Uses Windows-integrated authentication and is
independent of the FPL_DB_USER / FPL_DB_PASSWORD credentials the
pipeline itself uses (see db.py) -- this is a host/driver check, not a
pipeline credential check.

(Renamed from the original connection-test.py: a hyphen isn't valid in
a Python module name, so the old filename couldn't be imported --
only ever run directly, which this preserves.)
"""
from __future__ import annotations

import pyodbc

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=fpl;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def check_connection() -> None:
    """Open a connection and run a trivial query to confirm connectivity."""
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    print(cursor.fetchone())


if __name__ == "__main__":
    check_connection()
