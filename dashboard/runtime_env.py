"""Make Streamlit secrets available as environment variables.

Locally, settings come from ``.env``. On Streamlit Community Cloud they are
entered as the app's *secrets* instead; copying the top-level ones into the
environment means the dashboard and the code it shares with the pipeline
(``extraction/db.py``) read their settings the same way everywhere.
Variables already set in the environment win. Importing this module does it.
"""

from __future__ import annotations

import os


def load_secrets_into_env() -> None:
    try:
        import streamlit as st

        if hasattr(st.secrets, "load_if_toml_exists") and not st.secrets.load_if_toml_exists():
            return
        secrets = dict(st.secrets)
    except Exception:  # no secrets file, or not running under Streamlit
        return
    for key, value in secrets.items():
        if isinstance(value, str | int | float | bool) and key not in os.environ:
            os.environ[key] = str(value)


load_secrets_into_env()
