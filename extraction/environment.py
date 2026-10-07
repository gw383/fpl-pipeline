"""Live or dev: which copy of the warehouse and of the dashboard's data file
is in use.

One setting, ``FPL_ENV``, decides both, so they can't be switched
separately by mistake:

=========  ==============================  ==================
FPL_ENV    database                        data file's branch
=========  ==============================  ==================
``live``   ``FPL_DB_NAME``                 ``data``
``dev``    ``FPL_DB_NAME`` + ``_dev``      ``data-dev``
=========  ==============================  ==================

It defaults to ``live``. ``FPL_DB_NAME_DEV`` names the dev database
explicitly if ``<name>_dev`` doesn't suit. Everything else (server, logins)
is shared. The dbt profile in ``transformation/profiles`` applies the same
rule, so dbt builds into the same database the rest of the pipeline uses.

No dependencies, so every part of the project can import it.
"""

from __future__ import annotations

import os

LIVE = "live"
DEV = "dev"
ENVIRONMENTS = (LIVE, DEV)
DEFAULT_DATABASE = "FPL"


def current(environ: dict[str, str] | None = None) -> str:
    """The environment in use: ``live`` unless ``FPL_ENV`` says ``dev``."""
    env = os.environ if environ is None else environ
    value = (env.get("FPL_ENV") or LIVE).strip().lower()
    if value not in ENVIRONMENTS:
        raise ValueError(f"FPL_ENV is {value!r}: it must be one of {', '.join(ENVIRONMENTS)}.")
    return value


def database_name(environ: dict[str, str] | None = None) -> str:
    """The database for the environment in use."""
    env = os.environ if environ is None else environ
    live = env.get("FPL_DB_NAME") or DEFAULT_DATABASE
    if current(env) != DEV:
        return live
    dev = env.get("FPL_DB_NAME_DEV") or f"{live}_dev"
    if dev.strip().lower() == live.strip().lower():  # SQL Server names aren't case-sensitive
        raise ValueError(f"FPL_DB_NAME_DEV is the same database as FPL_DB_NAME ({live}): dev needs its own.")
    return dev
