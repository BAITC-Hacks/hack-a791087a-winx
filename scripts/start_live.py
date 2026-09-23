"""Start the local app with a hidden API-key prompt, without saving the key."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import warnings


ROOT = Path(__file__).resolve().parents[1]
GRACEFUL_SHUTDOWN_SECONDS = 5
FORCED_SHUTDOWN_SECONDS = 2
TASKKILL_TIMEOUT_SECONDS = 3
WAIT_POLL_SECONDS = 0.25


def _signal_process_group(process: subprocess.Popen) -> None:
    """Ask only this launcher's process group to stop cleanly."""
    if os.name == 'nt':
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        os.killpg(process.pid, signal.SIGINT)


def _wait_bounded(process: subprocess.Popen, timeout: float) -> int:
    """Wait no longer than timeout, even if the user presses Ctrl+C again."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout)
        try:
            return process.wait(timeout=remaining)
        except KeyboardInterrupt:
            continue


def _wait_interruptibly(process: subprocess.Popen) -> int:
    """Poll so Windows can deliver SIGINT while Popen waits for its child."""
    while True:
        try:
            return process.wait(timeout=WAIT_POLL_SECONDS)
        except subprocess.TimeoutExpired:
            continue


def _force_stop_process_tree(process: subprocess.Popen) -> None:
    """Kill only the launched process and its descendants after graceful timeout."""
    if os.name == 'nt':
        system_root = os.environ.get('SystemRoot', r'C:\Windows')
        taskkill = Path(system_root) / 'System32' / 'taskkill.exe'
        subprocess.run(
            [str(taskkill), '/PID', str(process.pid), '/T', '/F'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=TASKKILL_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    else:
        os.killpg(process.pid, signal.SIGKILL)


def _stop_after_interrupt(process: subprocess.Popen) -> None:
    previous_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        try:
            _signal_process_group(process)
        except OSError:
            pass

        try:
            _wait_bounded(process, GRACEFUL_SHUTDOWN_SECONDS)
            return
        except subprocess.TimeoutExpired:
            pass

        try:
            _force_stop_process_tree(process)
            _wait_bounded(process, FORCED_SHUTDOWN_SECONDS)
        except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            print('The app process did not stop cleanly; check its process tree.', file=sys.stderr)
    finally:
        signal.signal(signal.SIGINT, previous_sigint_handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default=os.getenv('OPENAI_MODEL', ''),
                        help='Responses API model ID available to your project')
    parser.add_argument('--port', type=int, default=8501)
    parser.add_argument('--headless', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    runtime = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not runtime.is_file():
        parser.error('First install and verify the app: python run.py --check')
    if sys.stdin is None or not sys.stdin.isatty():
        parser.error('Run this command in an interactive terminal; do not pipe a key into it.')

    try:
        model = args.model.strip() or input('OpenAI model ID available to your project: ').strip()
        if not model:
            parser.error('A model ID is required.')
        with warnings.catch_warnings():
            # getpass must never fall back to visible/echoed input.
            warnings.simplefilter('error', getpass.GetPassWarning)
            key = getpass.getpass('OpenAI API key (hidden; not saved): ').strip()
    except getpass.GetPassWarning:
        parser.error('Hidden input is unavailable. Use a normal interactive terminal.')
    except (EOFError, KeyboardInterrupt):
        return 130
    if not key:
        parser.error('No key entered; the app was not started.')

    child_env = {**os.environ, 'OPENAI_API_KEY': key, 'OPENAI_MODEL': model, 'DEMO_MODE': '0'}
    key = ''
    command = [
        str(runtime), '-m', 'streamlit', 'run', str(ROOT / 'app.py'),
        '--server.address=127.0.0.1', f'--server.port={args.port}',
        f"--server.headless={'true' if args.headless else 'false'}",
    ]
    print('Starting local live mode. API requests occur only on an AI button action.')
    try:
        process_options = (
            {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
            if os.name == 'nt'
            else {'start_new_session': True}
        )
        process = subprocess.Popen(command, cwd=ROOT, env=child_env, **process_options)
        try:
            return _wait_interruptibly(process)
        except KeyboardInterrupt:
            _stop_after_interrupt(process)
            return 130
    except OSError:
        print('Unable to start the app. Run python run.py --check first.', file=sys.stderr)
        return 1
    finally:
        child_env.pop('OPENAI_API_KEY', None)


if __name__ == '__main__':
    raise SystemExit(main())
