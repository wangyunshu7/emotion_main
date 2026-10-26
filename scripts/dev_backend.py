"""Run API and worker together for local development; Ctrl+C stops both."""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--port", default="8000")
args = parser.parse_args()
backend = Path(__file__).resolve().parents[1] / "backend"
processes = []
try:
    for command in (
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            args.port,
            "--no-access-log",
        ],
        [sys.executable, "-m", "app.jobs.runner"],
    ):
        processes.append(
            subprocess.Popen(
                command,
                cwd=backend,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        )
    while all(p.poll() is None for p in processes):
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    for process in processes:
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
