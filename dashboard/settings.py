"""Dashboard settings, overridable via environment variables / ``.env``."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

import runtime_env  # noqa: F401  -- Streamlit secrets -> environment (hosted app)

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction"))
from environment import LIVE, current  # noqa: E402

# live or dev (FPL_ENV): which data file and database this copy uses.
ENVIRONMENT = current()

ASSETS_DIR = Path(__file__).parent / "assets"
BADGES_DIR = ASSETS_DIR / "badges"
PITCH_IMAGE = ASSETS_DIR / "pitch.jpg"
LOGO = ASSETS_DIR / "logo.svg"
ICON = ASSETS_DIR / "icon.png"

# The FPL manager the My Team page opens on. Any other manager ID can be
# entered on the page, and is fetched from the FPL API if it isn't in the
# warehouse yet.
MY_ENTRY_ID = int(os.getenv("FPL_MY_ENTRY_ID", "194625"))

# How long query results are cached (seconds). They're also dropped as soon
# as a new data file is picked up.
CACHE_TTL_SECONDS = 600

# How often to check whether the pipeline has produced a new data file.
DATA_REFRESH_SECONDS = 900

PAGE_TITLE = "FPL Analytics" if ENVIRONMENT == LIVE else f"FPL Analytics ({ENVIRONMENT})"
REPO_URL = "https://github.com/gw383/fpl-pipeline"
