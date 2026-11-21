"""Run the local API and UI together and reap their process groups on exit."""

import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"
BACKEND_PORT = 8000
FRONTEND_PORT = 3000


def port_open(port: int) -> bool:
    with socket.socket() as connection:
        connection.settimeout(0.2)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def stop_old_frontend() -> None:
    if not port_open(FRONTEND_PORT):
        return
    listeners = subprocess.run(
        ["lsof", "-t", f"-iTCP:{FRONTEND_PORT}", "-sTCP:LISTEN"],
        capture_output=True, text=True, check=False,
    ).stdout.split()
    for pid in set(listeners):
        directory = subprocess.run(
            ["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
            capture_output=True, text=True, check=False,
        ).stdout.splitlines()
        command = subprocess.run(
            ["ps", "-p", pid, "-o", "command="],
            capture_output=True, text=True, check=False,
        ).stdout
        if f"n{FRONTEND.resolve()}" not in directory or "next" not in command.lower():
            raise RuntimeError(f"Port {FRONTEND_PORT} is in use by another process.")
        try:
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _ in range(25):
        if not port_open(FRONTEND_PORT):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Port {FRONTEND_PORT} is still in use.")


def stop_children(children: list[subprocess.Popen]) -> None:
    for child in reversed(children):
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    for child in reversed(children):
        try:
            child.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()


def wait_for_backend(child: subprocess.Popen) -> None:
    for _ in range(75):
        if child.poll() is not None:
            raise RuntimeError("FastAPI exited before it was ready.")
        try:
            with urlopen(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=0.3) as reply:
                if reply.status == 200:
                    return
        except URLError:
            time.sleep(0.2)
    raise RuntimeError("FastAPI did not respond to /health.")


def interrupted(_signum, _frame) -> None:
    raise KeyboardInterrupt


def main() -> int:
    venv_python = BACKEND / ".venv" / "bin" / "python"
    python = os.getenv("QAQPAN_PYTHON") or (
        str(venv_python) if venv_python.is_file() else sys.executable
    )
    children = []
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if port_open(BACKEND_PORT):
            raise RuntimeError(f"Port {BACKEND_PORT} is in use.")
        stop_old_frontend()
        seed = subprocess.Popen([python, "-m", "app.seed"], cwd=BACKEND, start_new_session=True)
        children.append(seed)
        if seed.wait() != 0:
            return seed.returncode
        children.remove(seed)
        api = subprocess.Popen(
            [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
            cwd=BACKEND, start_new_session=True,
        )
        children.append(api)
        wait_for_backend(api)
        children.append(subprocess.Popen(
            ["npm", "run", "dev", "--", "-p", str(FRONTEND_PORT), "--hostname", "127.0.0.1"],
            cwd=FRONTEND, start_new_session=True,
        ))
        while all(child.poll() is None for child in children):
            time.sleep(0.2)
        return next(child.returncode for child in children if child.returncode is not None)
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        stop_children(children)


if __name__ == "__main__":
    raise SystemExit(main())
