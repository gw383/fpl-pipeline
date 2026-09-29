"""Locate the project from a launcher script or a PyInstaller-built .exe."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    """The fpl-pipeline folder: ``FPL_PROJECT_ROOT`` if set, otherwise the
    nearest parent of this script (or of the .exe) containing ``dashboard/``."""
    if override := os.getenv("FPL_PROJECT_ROOT"):
        return Path(override)
    start = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    for folder in (start, *start.parents):
        if (folder / "dashboard" / "app.py").exists():
            return folder
    raise FileNotFoundError("Couldn't find the project folder; set FPL_PROJECT_ROOT.")


def venv_executable(root: Path, name: str) -> Path:
    """Path to a console script inside the project's ``venv``."""
    scripts = root / "venv" / ("Scripts" if os.name == "nt" else "bin")
    return scripts / (f"{name}.exe" if os.name == "nt" else name)
