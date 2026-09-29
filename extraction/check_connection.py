"""Quick connectivity check: ``python extraction/check_connection.py``.

Uses exactly the same connection settings as the pipeline (see db.py), so a
successful run means ``ingest.py`` will be able to reach the database too.
"""

from __future__ import annotations

from sqlalchemy import text

from db import build_connection_string, get_engine


def check_connection() -> None:
    """Open a connection, run ``SELECT @@VERSION`` and print the result."""
    safe = ";".join(part for part in build_connection_string().split(";") if not part.upper().startswith("PWD="))
    print(f"Connecting with: {safe}")
    with get_engine().connect() as conn:
        version = conn.execute(text("SELECT @@VERSION")).scalar_one()
    print("Connected OK.")
    print(version.splitlines()[0])


if __name__ == "__main__":
    check_connection()
