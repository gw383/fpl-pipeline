"""White "card" containers -- st.container with a key the site CSS styles."""

import re

import streamlit as st


def card(key: str, **kwargs):
    """A bordered container styled as a card. ``key`` must be unique on the page."""
    return st.container(border=True, key=f"card-{re.sub(r'[^A-Za-z0-9_-]', '-', str(key))}", **kwargs)
