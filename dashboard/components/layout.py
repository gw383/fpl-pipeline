"""Containers that change how st.columns behave on phones.

Below 640px wide Streamlit stacks every set of columns one per row. Columns
created inside these containers behave differently there (the CSS is in
theme.py); on wider screens they're ordinary columns.
"""

import re

import streamlit as st


def _key(prefix: str, key: str) -> str:
    return f"{prefix}-{re.sub(r'[^A-Za-z0-9_-]', '-', str(key))}"


def side_by_side(key: str):
    """Columns stay side by side on phones, shrinking to fit (e.g. Compare)."""
    return st.container(key=_key("sbs", key))


def two_per_row(key: str):
    """Columns wrap two per row on phones instead of one."""
    return st.container(key=_key("grid2", key))


def metrics_container(key: str):
    """Stat-card rows: two per row on phones, one per row inside side_by_side."""
    return st.container(key=_key("metrics", key))
