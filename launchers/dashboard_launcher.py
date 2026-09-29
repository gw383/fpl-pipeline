"""Desktop launcher: starts the Streamlit dashboard and opens it in a browser.

Build a standalone .exe with ``pyinstaller launchers/dashboard_launcher.spec``.
"""

from __future__ import annotations

import subprocess
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox

from _paths import project_root, venv_executable

DASHBOARD_URL = "http://localhost:8501"
STARTUP_DELAY_SECONDS = 3


def open_dashboard() -> None:
    """Start Streamlit from the project venv, then open the dashboard."""
    try:
        dashboard_dir = project_root() / "dashboard"
        streamlit = venv_executable(project_root(), "streamlit")
        subprocess.Popen([str(streamlit), "run", "app.py", "--server.headless=true"], cwd=dashboard_dir)
        time.sleep(STARTUP_DELAY_SECONDS)
        webbrowser.open(DASHBOARD_URL)
    except Exception as exc:  # surface any failure to the user
        messagebox.showerror("Dashboard Error", f"Could not start the dashboard.\n\n{exc}")


def build_window() -> tk.Tk:
    root = tk.Tk()
    root.title("FPL Dashboard")
    root.geometry("400x200")
    root.resizable(False, False)
    tk.Label(root, text="FPL Dashboard", font=("Arial", 20, "bold")).pack(pady=35)
    tk.Button(root, text="Open Dashboard", command=open_dashboard, width=20, height=2).pack()
    return root


if __name__ == "__main__":
    build_window().mainloop()
