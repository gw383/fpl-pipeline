"""Quick connectivity check: ``python extraction/check_connection.py``.

Uses exactly the same connection settings as the pipeline (see db.py), so a
successful run means ``ingest.py`` will be able to reach the database too.
"""

from __future__ import annotations

from sqlalchemy import text

from db import DbSettings, get_engine, wait_until_ready


def check_connection() -> None:
    """Open a connection, run ``SELECT @@VERSION`` and print the result."""
    s = DbSettings.from_env()
    login = s.user or "Windows authentication"
    print(f"Connecting to {s.server} / {s.database} as {login} (driver: {s.driver})")
    engine = get_engine(s)
    wait_until_ready(engine)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT @@VERSION")).scalar_one()
    print("Connected OK.")
    print(version.splitlines()[0])


if __name__ == "__main__":
    check_connection()
