"""
Shared fixtures for the integration suite (requires a live CockroachDB at
COCKROACH_DATABASE_URL). Both test modules use the `correlation_id` cleanup
fixture; the chaos test additionally spawns real uvicorn subprocesses to kill.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import uuid

import httpx
import psycopg
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)  # so `scripts.chaos_kill` imports in the chaos test


@pytest.fixture
def correlation_id():
    """A correlation_id unique to this test run, cleaned up afterwards so
    repeat CI runs against the same cluster don't accumulate rows."""
    cid = f"itest-{uuid.uuid4()}"
    yield cid
    with psycopg.connect(os.environ["COCKROACH_DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM remediation_steps WHERE incident_id IN "
            "(SELECT incident_id FROM incidents WHERE correlation_id = %s)",
            (cid,),
        )
        cur.execute(
            "DELETE FROM incident_embeddings WHERE incident_id IN "
            "(SELECT incident_id FROM incidents WHERE correlation_id = %s)",
            (cid,),
        )
        cur.execute("DELETE FROM incidents WHERE correlation_id = %s", (cid,))
        conn.commit()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class ApiProcess:
    """A uvicorn subprocess running api.main:app — a real, killable process."""

    def __init__(self, step_execution_seconds: float, port: int | None = None):
        self.port = port or _free_port()
        self._step = step_execution_seconds
        self.proc: subprocess.Popen | None = None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 40.0) -> "ApiProcess":
        env = dict(os.environ)
        env["STEP_EXECUTION_SECONDS"] = str(self._step)  # override CI's global 0
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app",
             "--host", "127.0.0.1", "--port", str(self.port), "--log-level", "warning"],
            cwd=REPO_ROOT, env=env,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if httpx.get(f"{self.base}/api/v1/health", timeout=1).status_code == 200:
                    return self
            except Exception:
                pass
            if self.proc.poll() is not None:
                raise RuntimeError(f"uvicorn on :{self.port} exited early ({self.proc.returncode})")
            time.sleep(0.3)
        raise RuntimeError(f"uvicorn on :{self.port} did not become healthy in {timeout}s")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                pass


@pytest.fixture
def api_factory():
    """Factory that spawns uvicorn API subprocesses and tears them all down."""
    servers: list[ApiProcess] = []

    def _make(step_execution_seconds: float = 4.0, port: int | None = None) -> ApiProcess:
        srv = ApiProcess(step_execution_seconds, port).start()
        servers.append(srv)
        return srv

    yield _make
    for srv in servers:
        srv.stop()
