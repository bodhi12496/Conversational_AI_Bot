"""Start a temporary app, verify the API + browser workflow, then stop it."""

import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="coe-verify-") as data_dir:
    env = dict(
        os.environ,
        COE_DATA_DIR=data_dir,
        COE_PROVIDER="demo",
        COE_API_TOKEN="",
        COE_BASE_URL="http://127.0.0.1:8017",
        PYTHONPATH=str(ROOT / "backend"),
    )
    server_python = os.getenv("COE_SERVER_PYTHON", sys.executable)
    server = subprocess.Popen(
        [
            server_python,
            "-m",
            "uvicorn",
            "app.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "8017",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 20
        while True:
            if server.poll() is not None:
                raise RuntimeError(server.stderr.read().decode())
            try:
                urllib.request.urlopen(env["COE_BASE_URL"] + "/health", timeout=1).close()
                break
            except (urllib.error.URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Server did not become ready.") from None
                time.sleep(0.2)
        subprocess.run([sys.executable, "scripts/demo.py"], cwd=ROOT, env=env, check=True)
        if "--dom" in sys.argv:
            subprocess.run(["npm", "run", "test:integration"], cwd=ROOT / "frontend", env=env, check=True)
        else:
            subprocess.run([sys.executable, "scripts/smoke_ui.py"], cwd=ROOT, env=env, check=True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
