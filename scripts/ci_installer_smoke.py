from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8080"
NODE = "node"
CLI = ROOT / "bin" / "cli.js"


def http_json(path: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        URL + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="GET" if data is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def health() -> bool:
    try:
        body = http_json("/api/v1/health")
        return body.get("ok") is True and body.get("service") == "OSH Agriculture AI Global"
    except Exception:
        return False


def wait_health(
    process: subprocess.Popen,
    log_path: Path,
    timeout: int = 360,
    require_restart: bool = False,
):
    deadline = time.time() + timeout

    # update must stop the previous server before a new healthy server appears.
    if require_restart:
        while time.time() < deadline and health():
            if process.poll() is not None:
                break
            time.sleep(1)
        if health():
            raise RuntimeError("Update never stopped the already-running web server.")

    while time.time() < deadline:
        if health():
            return
        if process.poll() is not None:
            break
        time.sleep(2)
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    raise RuntimeError(
        f"Installer/server did not become healthy. exit={process.poll()}\n"
        f"--- launcher log (last 12000 chars) ---\n{log[-12000:]}"
    )


def start_foreground(command: str, env: dict, log_path: Path):
    log_handle = log_path.open("ab")
    process = subprocess.Popen(
        [NODE, str(CLI), command, "--no-open"],
        cwd=ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    # The child inherits the OS handle; close the parent's copy.
    log_handle.close()
    wait_health(process, log_path, require_restart=(command == "update"))
    return process


def cli(command: str, env: dict):
    result = subprocess.run(
        [NODE, str(CLI), command, "--no-open"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError(
            f"CLI command '{command}' failed ({result.returncode})\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout + result.stderr


def stop_and_wait(process: subprocess.Popen, env: dict):
    output = cli("stop", env)
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
        raise RuntimeError("Foreground CLI did not exit after stop.")
    if health():
        raise RuntimeError("Health endpoint still responds after stop.")
    return output


def main():
    home = Path(tempfile.mkdtemp(prefix="osh-agri-installer-ci-"))
    logs = home / "ci-logs"
    logs.mkdir()
    log_path = logs / "launcher.log"

    env = os.environ.copy()
    env["OSH_AGRI_HOME"] = str(home / "app")
    # On PRs, exercise the exact branch under test, not main before merge.
    env.setdefault("OSH_AGRI_SOURCE_REF", os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF_NAME", "main"))

    launcher = None
    try:
        print("E2E 1/6: fresh install", flush=True)
        launcher = start_foreground("install", env, log_path)
        status = cli("status", env)
        if "Web: RUNNING" not in status or "Worker: RUNNING" not in status:
            raise RuntimeError(f"Web/worker status incorrect after install:\n{status}")

        print("E2E 2/6: register user and persist data", flush=True)
        email = "ci-installer@example.test"
        registered = http_json(
            "/api/v1/auth/register",
            {"email": email, "password": "installer-ci-password-123"},
        )
        if not registered.get("access_token"):
            raise RuntimeError("Registration did not return an access token.")

        print("E2E 3/6: stop web and worker", flush=True)
        stop_and_wait(launcher, env)
        launcher = None
        status = cli("status", env)
        if "Web: STOPPED" not in status or "Worker: STOPPED" not in status:
            raise RuntimeError(f"Web/worker status incorrect after stop:\n{status}")

        print("E2E 4/6: start existing installation", flush=True)
        launcher = start_foreground("start", env, log_path)
        login = http_json(
            "/api/v1/auth/login",
            {"email": email, "password": "installer-ci-password-123"},
        )
        if not login.get("access_token"):
            raise RuntimeError("Existing local user was not preserved after restart.")

        print("E2E 5/6: update running installation and preserve database", flush=True)
        # update itself stops the active app, refreshes source/runtime, then starts it again.
        update_launcher = start_foreground("update", env, log_path)
        launcher = update_launcher
        login = http_json(
            "/api/v1/auth/login",
            {"email": email, "password": "installer-ci-password-123"},
        )
        if not login.get("access_token"):
            raise RuntimeError("SQLite user data was not preserved by update.")

        print("E2E 6/6: final stop and clean status", flush=True)
        stop_and_wait(launcher, env)
        launcher = None
        status = cli("status", env)
        if "Web: STOPPED" not in status or "Worker: STOPPED" not in status:
            raise RuntimeError(f"Final status incorrect:\n{status}")

        print("PASS: install, web, worker, register, start, update, persistence, stop", flush=True)
    finally:
        if launcher is not None:
            try:
                subprocess.run(
                    [NODE, str(CLI), "stop", "--no-open"],
                    cwd=ROOT, env=env, text=True, capture_output=True, timeout=60
                )
            except Exception:
                pass
            try:
                launcher.wait(timeout=10)
            except Exception:
                launcher.kill()
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr, flush=True)
        raise
