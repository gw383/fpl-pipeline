"""Desktop launcher: "FPL Pipeline".

A minimal Tkinter window with one button that brings up the Airflow
Docker Compose stack (if it isn't already running) and triggers the
fpl_pipeline DAG, then opens the Airflow UI to watch it run. Packaged
into a standalone .exe with PyInstaller (see run_pipeline.spec).
"""
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox

AIRFLOW_DIR = r"C:\fpl-pipeline\airflow"
AIRFLOW_URL = "http://localhost:8080"
DAG_ID = "fpl_pipeline"

# Seconds to give the Airflow containers to come up before triggering the DAG.
AIRFLOW_STARTUP_DELAY_SECONDS = 10


def start_airflow() -> bool:
    """Bring up the Airflow Docker Compose stack if it isn't already running.

    Returns True if Airflow is (or is now) running, False if it failed
    to start.
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "-q", "airflow-apiserver"],
            cwd=AIRFLOW_DIR,
            capture_output=True,
            text=True,
        )

        if not result.stdout.strip():
            status_label.config(text="Starting Airflow...")
            subprocess.Popen(["docker", "compose", "up", "-d"], cwd=AIRFLOW_DIR)
            time.sleep(AIRFLOW_STARTUP_DELAY_SECONDS)

        return True

    except Exception as e:
        messagebox.showerror("Airflow Error", f"Could not start Airflow:\n\n{e}")
        return False


def trigger_pipeline() -> None:
    """Start Airflow if needed, trigger the DAG, and open the Airflow UI.

    Runs on a background thread so the Tkinter window stays responsive.
    """
    status_label.config(text="Starting pipeline...")
    run_button.config(state="disabled")

    def run_pipeline_thread() -> None:
        if not start_airflow():
            run_button.config(state="normal")
            return

        try:
            status_label.config(text="Triggering FPL pipeline...")

            result = subprocess.run(
                ["docker", "compose", "exec", "airflow-worker", "airflow", "dags", "trigger", DAG_ID],
                cwd=AIRFLOW_DIR,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise Exception(result.stderr or result.stdout)

            status_label.config(text="Pipeline started - opening Airflow...")
            time.sleep(2)
            webbrowser.open(AIRFLOW_URL)
            status_label.config(text="Pipeline running - monitor progress in Airflow.")

        except Exception as e:
            status_label.config(text="Pipeline failed to start.")
            messagebox.showerror("Pipeline Error", str(e))

        finally:
            run_button.config(state="normal")

    threading.Thread(target=run_pipeline_thread, daemon=True).start()


def build_window() -> tk.Tk:
    """Build the launcher window and its widgets (module-level globals
    used by trigger_pipeline/start_airflow, matching the original design).
    """
    global run_button, status_label

    root = tk.Tk()
    root.title("FPL Pipeline")
    root.geometry("450x250")
    root.resizable(False, False)

    title = tk.Label(root, text="FPL Pipeline", font=("Arial", 22, "bold"))
    title.pack(pady=(30, 10))

    description = tk.Label(
        root,
        text="Run the complete FPL ingestion and transformation pipeline.",
        font=("Arial", 10),
        wraplength=380,
    )
    description.pack(pady=(0, 25))

    run_button = tk.Button(
        root,
        text="Run Pipeline",
        command=trigger_pipeline,
        width=25,
        height=2,
        font=("Arial", 11, "bold"),
    )
    run_button.pack()

    status_label = tk.Label(root, text="Ready", font=("Arial", 10))
    status_label.pack(pady=20)

    return root


if __name__ == "__main__":
    build_window().mainloop()
