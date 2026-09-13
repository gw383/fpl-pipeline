"""Desktop launcher: "FPL Dashboard".

A minimal Tkinter window with one button that starts the Streamlit
app (via the project's venv) and opens it in the default browser.
Packaged into a standalone .exe with PyInstaller (see "FPL Dashboard.spec").
"""
import subprocess
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox

STREAMLIT_DIR = r"C:\fpl-pipeline\streamlit"
STREAMLIT_FILE = r"C:\fpl-pipeline\streamlit\home.py"
STREAMLIT_EXE = r"C:\fpl-pipeline\venv\Scripts\streamlit.exe"
STREAMLIT_URL = "http://localhost:8501"

# Seconds to wait for the Streamlit server to come up before opening
# the browser tab.
STARTUP_DELAY_SECONDS = 3


def open_dashboard() -> None:
    """Start Streamlit (from the project's venv) and open it in a browser tab."""
    try:
        subprocess.Popen(
            [STREAMLIT_EXE, "run", STREAMLIT_FILE, "--server.headless=true"],
            cwd=STREAMLIT_DIR,
        )
        time.sleep(STARTUP_DELAY_SECONDS)
        webbrowser.open(STREAMLIT_URL)

    except Exception as e:
        messagebox.showerror("Dashboard Error", f"Could not start the dashboard.\n\n{e}")


def build_window() -> tk.Tk:
    """Build the launcher window."""
    root = tk.Tk()
    root.title("FPL Dashboard")
    root.geometry("400x200")
    root.resizable(False, False)

    title = tk.Label(root, text="FPL Dashboard", font=("Arial", 20, "bold"))
    title.pack(pady=35)

    button = tk.Button(
        root, text="Open Dashboard", command=open_dashboard, width=20, height=2
    )
    button.pack()

    return root


if __name__ == "__main__":
    build_window().mainloop()
