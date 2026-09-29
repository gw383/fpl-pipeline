"""Desktop launcher: starts the Airflow stack (if needed), triggers the
``fpl_pipeline`` DAG and opens the Airflow UI.

Build a standalone .exe with ``pyinstaller launchers/pipeline_launcher.spec``.
"""

from __future__ import annotations

import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox

from _paths import project_root

AIRFLOW_URL = "http://localhost:8080"
DAG_ID = "fpl_pipeline"
AIRFLOW_STARTUP_DELAY_SECONDS = 10


class PipelineLauncher:
    def __init__(self) -> None:
        self.airflow_dir = project_root() / "airflow"
        self.root = tk.Tk()
        self.root.title("FPL Pipeline")
        self.root.geometry("450x250")
        self.root.resizable(False, False)

        tk.Label(self.root, text="FPL Pipeline", font=("Arial", 22, "bold")).pack(pady=(30, 10))
        tk.Label(
            self.root,
            text="Run the complete FPL ingestion and transformation pipeline.",
            font=("Arial", 10),
            wraplength=380,
        ).pack(pady=(0, 25))
        self.run_button = tk.Button(
            self.root, text="Run Pipeline", command=self.trigger, width=25, height=2, font=("Arial", 11, "bold")
        )
        self.run_button.pack()
        self.status = tk.Label(self.root, text="Ready", font=("Arial", 10))
        self.status.pack(pady=20)

    def _set_status(self, text: str) -> None:
        # Tk widgets must only be touched from the main thread.
        self.root.after(0, lambda: self.status.config(text=text))

    def _compose(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["docker", "compose", *args], cwd=self.airflow_dir, capture_output=True, text=True)

    def _run(self) -> None:
        try:
            if not self._compose("ps", "-q", "airflow-apiserver").stdout.strip():
                self._set_status("Starting Airflow...")
                subprocess.Popen(["docker", "compose", "up", "-d"], cwd=self.airflow_dir)
                time.sleep(AIRFLOW_STARTUP_DELAY_SECONDS)

            self._set_status("Triggering FPL pipeline...")
            result = self._compose("exec", "airflow-worker", "airflow", "dags", "trigger", DAG_ID)
            if result.returncode != 0:
                raise RuntimeError(result.stderr or result.stdout)

            self._set_status("Pipeline running - monitor progress in Airflow.")
            webbrowser.open(AIRFLOW_URL)
        except Exception as exc:  # surface any failure to the user
            message = str(exc)
            self._set_status("Pipeline failed to start.")
            self.root.after(0, lambda: messagebox.showerror("Pipeline Error", message))
        finally:
            self.root.after(0, lambda: self.run_button.config(state="normal"))

    def trigger(self) -> None:
        self.run_button.config(state="disabled")
        self.status.config(text="Starting pipeline...")
        threading.Thread(target=self._run, daemon=True).start()


if __name__ == "__main__":
    PipelineLauncher().root.mainloop()
