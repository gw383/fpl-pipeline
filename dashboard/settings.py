"""Dashboard settings, overridable via environment variables / ``.env``."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

import runtime_env  # noqa: F401  -- Streamlit secrets -> environment (hosted app)

load_dotenv()

ASSETS_DIR = Path(__file__).parent / "assets"
BADGES_DIR = ASSETS_DIR / "badges"
PITCH_IMAGE = ASSETS_DIR / "pitch.jpg"
LOGO = ASSETS_DIR / "logo.svg"
ICON = ASSETS_DIR / "icon.png"

# The FPL manager the My Team page opens on. Any other manager ID can be
# entered on the page, and is fetched from the FPL API if it isn't in the
# warehouse yet.
MY_ENTRY_ID = int(os.getenv("FPL_MY_ENTRY_ID", "194625"))

# How long query results are cached (seconds).
CACHE_TTL_SECONDS = 600

PAGE_TITLE = "FPL Analytics"
REPO_URL = "https://github.com/gw383/fpl-pipeline"
