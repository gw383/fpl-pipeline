
import tkinter as tk
from tkinter import messagebox
import subprocess
import webbrowser
import time


# -----------------------------
# Configuration
# -----------------------------

STREAMLIT_DIR = r"C:\fpl-pipeline\streamlit"
STREAMLIT_FILE = r"C:\fpl-pipeline\streamlit\home.py"
STREAMLIT_EXE = r"C:\fpl-pipeline\venv\Scripts\streamlit.exe"

STREAMLIT_URL = "http://localhost:8501"


# -----------------------------
# Open Dashboard
# -----------------------------

def open_dashboard():
    try:
        # Start Streamlit using the executable
        # from the Python virtual environment.
        subprocess.Popen(
            [
                STREAMLIT_EXE,
                "run",
                STREAMLIT_FILE,
                "--server.headless=true"
            ],
            cwd=STREAMLIT_DIR
        )

        # Give Streamlit a moment to start
        time.sleep(3)

        # Open dashboard in browser
        webbrowser.open(STREAMLIT_URL)

    except Exception as e:
        messagebox.showerror(
            "Dashboard Error",
            f"Could not start the dashboard.\n\n{e}"
        )


# -----------------------------
# Tkinter UI
# -----------------------------

root = tk.Tk()

root.title("FPL Dashboard")
root.geometry("400x200")
root.resizable(False, False)

title = tk.Label(
    root,
    text="FPL Dashboard",
    font=("Arial", 20, "bold")
)

title.pack(pady=35)

button = tk.Button(
    root,
    text="Open Dashboard",
    command=open_dashboard,
    width=20,
    height=2
)

button.pack()

root.mainloop()

