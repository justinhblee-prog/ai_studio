"""B-21: ONE command that brings the API up locally, in the free mock mode, and proves it answers.

   python scripts/dev_up.py                 start the API on 127.0.0.1:8000 with throw-away data under .dev_data/ (Ctrl+C stops it)
   python scripts/dev_up.py --selftest      start it on a free port with data in a temp folder, wait until /health and an authenticated call answer, print how long it took, stop it (CI runs this)
   python scripts/dev_up.py --check         only look at the prerequisites and say what is missing

Safe by construction: PROVIDER_MODE=mock (no AI service, no paid call), the server listens on 127.0.0.1 only, the data folder is local and ignored by git, the signing secret is random and lives only in
the server's memory, and the one sign-in token below is a PUBLIC dev value that only works against this local mock server (it is not a secret and opens nothing else). Nothing is read from or written to
Supabase, Vercel or any shared database.
The API code uses ``fcntl`` (Linux/macOS), so on Windows run this inside WSL (see docs/ONBOARDING.md).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DEV_TOKEN, DEV_USER = "local-dev-token", "dev-user"            # public, local-only
NEEDED_MODULES = ("fastapi", "uvicorn", "PIL", "httpx", "psycopg", "pydantic")


def prerequisites() -> list[str]:
    problems = []
    if sys.version_info < (3, 11):
        problems.append(f"Python 3.11 or newer is needed (this is {sys.version.split()[0]})")
    for name in NEEDED_MODULES:
        try:
            __import__(name)
        except ImportError:
            problems.append(f"missing Python package '{name}': run  pip install -r requirements.txt")
    try:
        import fcntl  # noqa: F401
    except ImportError:
        problems.append("this platform has no 'fcntl' (Windows): run inside WSL or on Linux/macOS (docs/ONBOARDING.md)")
    return problems


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def environment(data: Path) -> dict[str, str]:
    data.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({"PROVIDER_MODE": "mock", "ASSET_SIGNING_SECRET": secrets.token_hex(24), "ASSET_API_TOKENS": f"{DEV_TOKEN}:{DEV_USER}",
                "ASSET_STORAGE_DIR": str(data / "private"), "ASSET_DATABASE_PATH": str(data / "app.sqlite3"), "OUTPUT_DIR": str(data / "outputs"),
                "PYTHONPATH": os.pathsep.join([str(BACKEND)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else []))})
    env.pop("DATABASE_URL", None)                 # never let a shell variable point this at a real database
    env.pop("DATABASE_BACKEND", None)
    return env


def get(url: str, token: str | None = None, timeout: float = 3.0) -> tuple[int, dict]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def wait_until_up(base: str, process: subprocess.Popen, seconds: float) -> float:
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        if process.poll() is not None:
            raise RuntimeError(f"the server stopped by itself (exit {process.returncode})")
        try:
            if get(base + "/health")[0] == 200:
                return time.monotonic() - started
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        time.sleep(0.25)
    raise RuntimeError(f"/health did not answer within {seconds:.0f} s")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--wait", type=float, default=60.0)
    args = parser.parse_args(argv)
    problems = prerequisites()
    if problems:
        print("Cannot start yet:\n  - " + "\n  - ".join(problems))
        return 2
    if args.check:
        print("Prerequisites are fine.")
        return 0
    port = free_port() if args.selftest else args.port
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as temp:
        data = Path(temp) if args.selftest else BACKEND / ".dev_data"
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=BACKEND, env=environment(data))
        try:
            seconds = wait_until_up(base, process, args.wait)
            status, me = get(base + "/v1/auth/me", DEV_TOKEN)
            anonymous, _ = get(base + "/v1/auth/me")
            if status != 200 or anonymous != 401:
                print(f"UP, but the sign-in check is wrong: with the dev token {status}, without a token {anonymous} (expected 200 and 401)")
                return 1
            print(f"UP in {seconds:.1f} s: {base}  (API docs: {base}/docs; mock mode; sign in with the header  Authorization: Bearer {DEV_TOKEN})")
            if args.selftest:
                return 0
            print("Press Ctrl+C to stop.")
            process.wait()
            return process.returncode or 0
        except KeyboardInterrupt:
            return 0
        except RuntimeError as exc:
            print(f"FAILED: {exc}")
            return 1
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
