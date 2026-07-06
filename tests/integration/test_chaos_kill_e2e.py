"""
The real kill-and-recover cycle — the demo's centerpiece, as an automated test.

Unlike test_recovery_e2e.py (which injects the durable `executing` state with a
SQL UPDATE), this spawns the orchestrator as a real uvicorn subprocess, fires an
alert that blocks mid-step, and **hard-kills the process with scripts/chaos_kill.py**
(real SIGKILL/TerminateProcess, no graceful shutdown) while a step is genuinely
in flight. Then a fresh cold process resumes purely from CockroachDB.

Requires a live CockroachDB at COCKROACH_DATABASE_URL. AWS creds are NOT needed:
correlation is best-effort (ADR 009), so with absent/fake Bedrock creds the embed
call fails, is caught, and the step still reaches `executing`.

    COCKROACH_DATABASE_URL=... pytest tests/integration/test_chaos_kill_e2e.py -v
"""
from __future__ import annotations

import os
import threading
import time

import httpx
import psycopg
import pytest

from agents.memory_agent import MemoryAgent
from config import settings
from scripts.chaos_kill import kill_by_port

pytestmark = pytest.mark.skipif(
    "COCKROACH_DATABASE_URL" not in os.environ,
    reason="requires a live CockroachDB instance — set COCKROACH_DATABASE_URL to run",
)


def _alert(correlation_id: str) -> dict:
    return {
        "correlation_id": correlation_id,
        "service": "checkout-api",
        "region": "eu-central-1",
        "severity": "high",
        "text": "Elevated p99 latency on checkout-api (chaos kill test)",
    }


def _poll_until(predicate, timeout: float = 30.0, interval: float = 0.25) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _executed_count(correlation_id: str) -> int:
    with psycopg.connect(os.environ["COCKROACH_DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM remediation_steps s JOIN incidents i "
            "ON i.incident_id = s.incident_id "
            "WHERE i.correlation_id = %s AND s.status = 'executed'",
            (correlation_id,),
        )
        return cur.fetchone()[0]


def test_real_kill_and_recover(correlation_id, api_factory):
    memory = MemoryAgent()
    alert = _alert(correlation_id)

    # 1. Real orchestrator process, with a long execution window to strike inside.
    srv = api_factory(step_execution_seconds=4.0)

    # 2. Fire the alert in the background — it blocks in the step's execution
    #    window (the POST connection drops when we kill the server, which is fine).
    def _fire():
        try:
            httpx.post(f"{srv.base}/api/v1/alert", json=alert, timeout=30)
        except Exception:
            pass

    threading.Thread(target=_fire, daemon=True).start()

    # 3. Wait until step 0 is DURABLY `executing` in CockroachDB, then hard-kill.
    def _executing() -> bool:
        st = memory.get_open_incident(correlation_id)
        return st is not None and st.last_step_index == 0 and st.last_step_status == "executing"

    assert _poll_until(_executing, timeout=30), "step 0 never reached 'executing'"

    killed = kill_by_port(srv.port)
    assert killed >= 1, "chaos_kill.py did not find the orchestrator process to kill"

    # 4. The interrupted step is still durably `executing` after the process died.
    st = memory.get_open_incident(correlation_id)
    assert st is not None and st.last_step_status == "executing"

    # 5. A fresh cold process resumes purely from CockroachDB.
    srv2 = api_factory(step_execution_seconds=0.0)
    resumed = httpx.post(f"{srv2.base}/api/v1/alert", json=alert, timeout=30).json()
    assert resumed["resumed"] is True
    assert resumed["step_index"] == 0, "must re-run the interrupted step, not skip to step 1"
    assert resumed["reexecuted_after_interrupt"] is True

    # 6. Drive to resolution; every step_index executed exactly once — no dup, no skip.
    state = resumed["state"]
    while state != "resolved":
        state = httpx.post(f"{srv2.base}/api/v1/alert", json=alert, timeout=30).json()["state"]

    assert _executed_count(correlation_id) == settings.max_remediation_steps
