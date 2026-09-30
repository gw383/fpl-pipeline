"""SQL Server connectivity, shared by the pipeline, the projection model and
the dashboard.

Settings come from environment variables (or a ``.env`` file; on Streamlit
Community Cloud, from the app's secrets):

``FPL_DB_SERVER``      server name (default ``localhost``); for Azure SQL,
                       ``<name>.database.windows.net``
``FPL_DB_NAME``        database (default ``FPL``)
``FPL_DB_USER``        SQL login; leave unset for Windows authentication
``FPL_DB_PASSWORD``    its password
``FPL_DB_PORT``        port (default 1433)
``FPL_DB_DRIVER``      ``odbc`` (default: Microsoft's ODBC Driver 18, via
                       pyodbc) or ``pymssql`` (pure pip install, no ODBC
                       driver -- what the hosted dashboard uses)
``FPL_DB_TRUST_CERT``  ``yes`` (default) to accept the server's certificate
                       without checking it, as a local SQL Server with a
                       self-signed certificate needs; ``no`` for Azure SQL
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

load_dotenv()

logger = logging.getLogger(__name__)

ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
AZURE_SUFFIX = ".database.windows.net"


@dataclass(frozen=True)
class DbSettings:
    server: str = "localhost"
    database: str = "FPL"
    user: str | None = None
    password: str = ""
    port: int = 1433
    driver: str = "odbc"
    trust_cert: bool = True

    @classmethod
    def from_env(cls) -> DbSettings:
        return cls(
            server=os.getenv("FPL_DB_SERVER") or "localhost",
            database=os.getenv("FPL_DB_NAME") or "FPL",
            user=os.getenv("FPL_DB_USER") or None,
            password=os.getenv("FPL_DB_PASSWORD") or "",
            port=int(os.getenv("FPL_DB_PORT") or 1433),
            driver=(os.getenv("FPL_DB_DRIVER") or "odbc").strip().lower(),
            trust_cert=(os.getenv("FPL_DB_TRUST_CERT") or "yes").strip().lower() in ("yes", "true", "1"),
        )

    @property
    def is_azure(self) -> bool:
        return self.server.lower().endswith(AZURE_SUFFIX)


def build_connection_string(settings: DbSettings | None = None) -> str:
    """The ODBC connection string (``odbc`` driver)."""
    s = settings or DbSettings.from_env()
    auth = f"UID={s.user};PWD={s.password};" if s.user else "Trusted_Connection=yes;"
    server = f"tcp:{s.server},{s.port}" if s.is_azure or s.port != 1433 else s.server
    return (
        f"DRIVER={{{ODBC_DRIVER}}};SERVER={server};DATABASE={s.database};{auth}"
        f"Encrypt=yes;TrustServerCertificate={'yes' if s.trust_cert else 'no'};Connection Timeout=60;"
    )


def build_url(settings: DbSettings | None = None) -> str:
    """The SQLAlchemy URL for the configured driver."""
    s = settings or DbSettings.from_env()
    if s.driver == "pymssql":
        if not s.user:
            raise ValueError("The pymssql driver needs a SQL login: set FPL_DB_USER and FPL_DB_PASSWORD.")
        user = s.user
        if s.is_azure and "@" not in user:
            # FreeTDS (inside pymssql) talks to Azure SQL most reliably as user@server.
            user = f"{user}@{s.server.split('.')[0]}"
        return (
            f"mssql+pymssql://{quote_plus(user)}:{quote_plus(s.password)}@{s.server}:{s.port}/{quote_plus(s.database)}"
        )
    if s.driver != "odbc":
        raise ValueError(f"Unknown FPL_DB_DRIVER {s.driver!r}: use 'odbc' or 'pymssql'.")
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(build_connection_string(s))}"


def get_engine(settings: DbSettings | None = None) -> Engine:
    """A SQLAlchemy engine for the FPL database.

    ``pool_pre_ping`` quietly replaces connections dropped while the
    database was idle (an Azure SQL free-tier database pauses itself). With
    pyodbc, ``fast_executemany`` sends each ``DataFrame.to_sql`` batch as a
    single round trip instead of one INSERT per row.
    """
    s = settings or DbSettings.from_env()
    kwargs: dict = {"pool_pre_ping": True}
    if s.driver == "odbc":
        kwargs["fast_executemany"] = True
    else:
        kwargs["connect_args"] = {"login_timeout": 60}  # a paused Azure database takes a while to answer
    return create_engine(build_url(s), **kwargs)


def wait_until_ready(engine: Engine, attempts: int = 6, delay_seconds: float = 20.0) -> None:
    """Open a connection, retrying while the database wakes up.

    An Azure SQL serverless (free tier) database pauses when idle and takes
    up to a minute to resume; the first connection attempts fail meanwhile.
    """
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("select 1"))
            return
        except DBAPIError as exc:
            if attempt == attempts:
                raise
            logger.info("Database not ready yet (attempt %d/%d): %s", attempt, attempts, str(exc).splitlines()[0])
            time.sleep(delay_seconds)
