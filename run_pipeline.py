import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import webbrowser
import time

AIRFLOW_DIR = r"C:\fpl-pipeline\airflow"
AIRFLOW_URL = "http://localhost:8080"
DAG_ID = "fpl_pipeline"

def start_airflow():
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "-q", "airflow-apiserver"],
            cwd=AIRFLOW_DIR,
            capture_output=True,
            text=True
        )

        if not result.stdout.strip():
            status_label.config(text="Starting Airflow...")
            subprocess.Popen(
                ["docker", "compose", "up", "-d"],
                cwd=AIRFLOW_DIR
            )
            time.sleep(10)

        return True

    except Exception as e:
        messagebox.showerror(
            "Airflow Error",
            f"Could not start Airflow:\n\n{e}"
        )
        return False

def trigger_pipeline():
    status_label.config(text="Starting pipeline...")
    run_button.config(state="disabled")

    def run_pipeline_thread():
        if not start_airflow():
            run_button.config(state="normal")
            return

        try:
            status_label.config(text="Triggering FPL pipeline...")

            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "airflow-worker",
                    "airflow",
                    "dags",
                    "trigger",
                    DAG_ID
                ],
                cwd=AIRFLOW_DIR,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise Exception(result.stderr or result.stdout)

            status_label.config(
                text="Pipeline started - opening Airflow..."
            )

            time.sleep(2)

            webbrowser.open(AIRFLOW_URL)

            status_label.config(
                text="Pipeline running - monitor progress in Airflow."
            )

        except Exception as e:
            status_label.config(
                text="Pipeline failed to start."
            )
            messagebox.showerror(
                "Pipeline Error",
                str(e)
            )

        finally:
            run_button.config(state="normal")

    threading.Thread(
        target=run_pipeline_thread,
        daemon=True
    ).start()

root = tk.Tk()
root.title("FPL Pipeline")
root.geometry("450x250")
root.resizable(False, False)

title = tk.Label(
    root,
    text="FPL Pipeline",
    font=("Arial", 22, "bold")
)
title.pack(pady=(30, 10))

description = tk.Label(
    root,
    text="Run the complete FPL ingestion and transformation pipeline.",
    font=("Arial", 10),
    wraplength=380
)
description.pack(pady=(0, 25))

run_button = tk.Button(
    root,
    text="Run Pipeline",
    command=trigger_pipeline,
    width=25,
    height=2,
    font=("Arial", 11, "bold")
)
run_button.pack()

status_label = tk.Label(
    root,
    text="Ready",
    font=("Arial", 10)
)
status_label.pack(pady=20)

root.mainloop()
