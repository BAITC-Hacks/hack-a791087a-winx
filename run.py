"""One-command local setup and launch, with no activation or Docker."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Install and run offline checks")
    parser.add_argument("--headless", action="store_true", help="Do not open a browser")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("Python 3.11 or newer is required")
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print("Creating .venv...", flush=True)
        venv.create(environment, with_pip=True)
    requirements = ROOT / "requirements.txt"
    signature = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = environment / ".requirements.sha256"
    if not marker.exists() or marker.read_text() != signature:
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirements)], cwd=ROOT, check=True)
        marker.write_text(signature)
    if args.check:
        env = {**os.environ, "DEMO_MODE": "1", "OPENAI_API_KEY": ""}
        return subprocess.call([str(python), "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, env=env)
    return subprocess.call([
        str(python), "-m", "streamlit", "run", "app.py",
        "--server.address=127.0.0.1", f"--server.port={args.port}",
        f"--server.headless={'true' if args.headless else 'false'}",
    ], cwd=ROOT)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
