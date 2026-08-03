"""
Capture a judge-facing kill-and-recover run into `assets/chaos-run/`.

`make chaos-demo` *drives* the kill; it does not record it. That gap is why
`assets/chaos-run/` held a plan and no runs: the evidence layout was documented
and then had to be assembled by hand afterwards, which is exactly how an
artifact ends up disagreeing with the run that produced it.

This script does both. It performs the same real kill as
`tests/integration/test_chaos_kill_e2e.py` — a genuine `SIGKILL`/`TerminateProcess`
delivered by `scripts/chaos_kill.py` to a live uvicorn orchestrator while a step
is in flight — and snapshots CockroachDB at each phase as it goes:

    01-before-kill      step N durably `executing`, process alive
    02-frozen           same row, process dead. **The whole thesis.**
    03-after-resume     step N re-run exactly once by a cold process, incident resolved

Everything it writes is read back out of the database, not inferred from a
return value, and every assertion that matters is enforced here rather than
left for a reader to check: if the kill lands outside the execution window, or a
step executes twice, the run **fails loudly and the folder is marked failed**
rather than quietly producing evidence of something weaker than it claims.

The incident is deliberately left in the cluster afterwards, and its id is
printed, so the console screenshots (`03`, `06` in the shot list) can show *this*
run's rows rather than some other incident's.

Usage:
    python scripts/chaos_capture.py                  # local process kill
    python scripts/chaos_capture.py --keep-logs      # keep raw uvicorn output too
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import httpx  # noqa: E402
import psycopg  # noqa: E402

from agents.memory_agent import MemoryAgent  # noqa: E402
from config import settings  # noqa: E402
from observability.structured_logger import get_logger  # noqa: E402
from scripts.chaos_kill import kill_by_port  # noqa: E402
from scripts.evidence import new_run  # noqa: E402

log = get_logger(__name__)

SERVICE = "checkout-api"
REGION = "eu-central-1"


class CaptureFailed(RuntimeError):
    """The run did not prove what it set out to prove."""


# --------------------------------------------------------------------------
# A real, killable orchestrator process — with its log captured to disk
# --------------------------------------------------------------------------
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Orchestrator:
    """uvicorn running api.main:app, with stdout/stderr teed into the evidence
    folder. The log is the invocation's own account of what it did, and the
    second process's copy of it is what shows the recovery read happening."""

    def __init__(self, step_seconds: float, log_path: Path):
        self.port = _free_port()
        self.step_seconds = step_seconds
        self.log_path = log_path
        self.proc: subprocess.Popen | None = None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 60.0) -> "Orchestrator":
        env = dict(os.environ)
        env["STEP_EXECUTION_SECONDS"] = str(self.step_seconds)
        self._fh = self.log_path.open("ab")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=REPO_ROOT,
            env=env,
            stdout=self._fh,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if httpx.get(f"{self.base}/api/v1/health", timeout=1).status_code == 200:
                    log.info("orchestrator_up", port=self.port, step_execution_seconds=self.step_seconds)
                    return self
            except Exception:  # noqa: BLE001 — still booting
                pass
            if self.proc.poll() is not None:
                raise CaptureFailed(f"uvicorn exited early with {self.proc.returncode}; see {self.log_path}")
            time.sleep(0.3)
        raise CaptureFailed(f"uvicorn on :{self.port} never became healthy in {timeout}s")

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if self.alive():
            self.proc.kill()
            try:
                self.proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                pass
        fh = getattr(self, "_fh", None)
        if fh and not fh.closed:
            fh.close()


# --------------------------------------------------------------------------
# Phase snapshots — read back out of CockroachDB, never inferred
# --------------------------------------------------------------------------
def snapshot(correlation_id: str, phase: str, note: str) -> dict:
    with psycopg.connect(settings.cockroach_database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT incident_id, correlation_id, service, region, severity, state, "
            "       summary, opened_at, updated_at, resolved_at "
            "FROM incidents WHERE correlation_id = %s",
            (correlation_id,),
        )
        cols = [c.name for c in cur.description]
        incident = dict(zip(cols, cur.fetchone(), strict=True)) if cur.rowcount else None

        steps = []
        if incident:
            cur.execute(
                "SELECT step_index, action, proposed_by, status, detail, created_at "
                "FROM remediation_steps WHERE incident_id = %s ORDER BY step_index",
                (incident["incident_id"],),
            )
            scols = [c.name for c in cur.description]
            steps = [dict(zip(scols, r, strict=True)) for r in cur.fetchall()]

    return {
        "phase": phase,
        "note": note,
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "incident": incident,
        "remediation_steps": steps,
        "step_status_counts": {
            s: sum(1 for x in steps if x["status"] == s) for s in sorted({x["status"] for x in steps})
        },
    }


def _probe_bedrock() -> tuple[str, bool]:
    """Which mode is this run in? Both Bedrock paths degrade silently (ADR 008),
    so a run that never touched Bedrock looks identical to one that did. Recorded
    either way — a fallback run is honest evidence, an unlabelled one is not."""
    try:
        r = subprocess.run(
            [sys.executable, "scripts/probe_bedrock.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return (r.stdout + r.stderr), r.returncode == 0
    except Exception as exc:  # noqa: BLE001 — never fatal to the capture
        return f"probe failed to run: {exc!r}", False


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------
def capture_local(step_seconds: float, keep_logs: bool) -> int:
    run = new_run("chaos", label="local")
    correlation_id = f"chaos-{uuid.uuid4().hex[:8]}"
    memory = MemoryAgent()
    alert = {
        "correlation_id": correlation_id,
        "service": SERVICE,
        "region": REGION,
        "severity": "high",
        "text": "Elevated p99 latency on checkout-api, connection pool saturated after deploy",
    }
    log_path = run.evidence / f"{run.short_id}_orchestrator-log.jsonl"
    phases: list[dict] = []
    results: dict = {"correlation_id": correlation_id, "mode": "local-process-kill"}

    print(f"\n=== chaos capture {run.short_id} · correlation_id={correlation_id} ===\n")

    probe_out, bedrock_ok = _probe_bedrock()
    run.write_text("bedrock-probe.txt", probe_out)
    results["bedrock_reachable_at_capture"] = bedrock_ok
    print(f"[0/6] bedrock probe: {'OK — live path available' if bedrock_ok else 'CLOSED — run will use fallbacks'}")

    srv1 = srv2 = None
    try:
        # 1. A real process, with an execution window wide enough to strike inside.
        srv1 = Orchestrator(step_seconds, log_path).start()
        results["killed_pid"] = srv1.proc.pid
        results["killed_port"] = srv1.port
        print(f"[1/6] orchestrator up on :{srv1.port} (pid {srv1.proc.pid}), step window {step_seconds}s")

        # 2. Fire the alert; it blocks inside the step's execution window. The
        #    POST connection dies with the process — expected, hence the catch.
        def _fire() -> None:
            try:
                httpx.post(f"{srv1.base}/api/v1/alert", json=alert, timeout=step_seconds + 60)
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_fire, daemon=True).start()

        # 3. Wait for the step to be DURABLY `executing` before killing. Striking
        #    earlier would prove nothing: the point is that the kill lands after
        #    the start-commit and before the done-commit (ADR 009).
        deadline = time.time() + 90
        interrupted_at = None
        while time.time() < deadline:
            st = memory.get_open_incident(correlation_id)
            if st is not None and st.last_step_status == "executing":
                interrupted_at = st.last_step_index
                break
            time.sleep(0.2)
        if interrupted_at is None:
            raise CaptureFailed("no step ever reached a durable 'executing' state — nothing to interrupt")
        results["interrupted_step_index"] = interrupted_at
        phases.append(snapshot(correlation_id, "01-before-kill", f"step {interrupted_at} executing; process alive"))
        print(f"[2/6] step {interrupted_at} is durably 'executing' in CockroachDB")

        # 4. The kill. No graceful shutdown, no cleanup handler, no checkpoint.
        killed = kill_by_port(srv1.port)
        if killed < 1:
            raise CaptureFailed("chaos_kill.py found no process to kill")
        time.sleep(1.0)
        if srv1.alive():
            raise CaptureFailed("process survived the kill — this run proves nothing")
        print(f"[3/6] SIGKILL delivered to pid {results['killed_pid']} — process is gone")

        # 5. The money shot: the row is still `executing` with nobody alive to own it.
        frozen = snapshot(
            correlation_id, "02-frozen", "process dead; interrupted step still 'executing' in CockroachDB"
        )
        phases.append(frozen)
        frozen_step = next((s for s in frozen["remediation_steps"] if s["step_index"] == interrupted_at), None)
        if frozen_step is None or frozen_step["status"] != "executing":
            raise CaptureFailed(f"interrupted step is not 'executing' after the kill: {frozen_step}")
        print("[4/6] CAPTURED: step frozen in 'executing' with no live process — screenshot this now if recording")

        # 6. A cold process resumes purely from CockroachDB.
        srv2 = Orchestrator(0.5, log_path).start()
        resumed = httpx.post(f"{srv2.base}/api/v1/alert", json=alert, timeout=120).json()
        results["resume_response"] = resumed
        if not resumed.get("resumed"):
            raise CaptureFailed(f"cold process did not report a resume: {resumed}")
        if resumed.get("step_index") != interrupted_at:
            raise CaptureFailed(f"resumed at step {resumed.get('step_index')}, expected {interrupted_at}")
        if not resumed.get("reexecuted_after_interrupt"):
            raise CaptureFailed("resume did not re-execute the interrupted step")
        print(f"[5/6] cold process resumed at step {interrupted_at} — the exact step it died on")

        # 7. Drive to resolution, then prove exactly-once from the durable rows.
        state = resumed["state"]
        guard = 0
        while state != "resolved" and guard < settings.max_remediation_steps + 3:
            state = httpx.post(f"{srv2.base}/api/v1/alert", json=alert, timeout=120).json()["state"]
            guard += 1
        after = snapshot(correlation_id, "03-after-resume", "incident resolved; every step executed exactly once")
        phases.append(after)

        indices = [s["step_index"] for s in after["remediation_steps"]]
        duplicated = sorted({i for i in indices if indices.count(i) > 1})
        executed = [s for s in after["remediation_steps"] if s["status"] == "executed"]
        results.update(
            {
                "final_state": after["incident"]["state"] if after["incident"] else None,
                "steps_executed": len(executed),
                "duplicated_step_indices": duplicated,
                "exactly_once": not duplicated and len(executed) == settings.max_remediation_steps,
            }
        )
        if duplicated:
            raise CaptureFailed(f"step(s) executed more than once: {duplicated} — exactly-once violated")
        if len(executed) != settings.max_remediation_steps:
            raise CaptureFailed(f"expected {settings.max_remediation_steps} executed steps, found {len(executed)}")
        print(f"[6/6] resolved · {len(executed)} steps executed · 0 duplicated · 0 lost")
        results["outcome"] = "PASS"
        return 0

    except CaptureFailed as exc:
        results["outcome"] = "FAIL"
        results["failure"] = str(exc)
        print(f"\nCAPTURE FAILED: {exc}\n", file=sys.stderr)
        return 1
    finally:
        for s in (srv1, srv2):
            if s:
                s.stop()
        for p in phases:
            run.write_json(f"{p['phase']}.json", p)
        run.write_json("remediation-steps.json", {"correlation_id": correlation_id, "phases": phases})
        run.write_json("session-metadata.json", results)
        run.write_text("NOTES.md", _notes(run.short_id, results, phases, bedrock_ok))
        if not keep_logs and log_path.exists() and results.get("outcome") == "PASS":
            # The uvicorn access log is noise; the structlog JSON lines are the
            # evidence. Keep only the latter unless asked for everything.
            lines = [
                ln for ln in log_path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.startswith("{")
            ]
            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        manifest = run.finalize(extra=results)
        print(f"\nevidence: {run.dir.relative_to(REPO_ROOT)}")
        print(f"manifest: {manifest.relative_to(REPO_ROOT)}")
        if results.get("outcome") == "PASS":
            print(
                f"\nThe incident is LEFT IN THE CLUSTER on purpose.\n"
                f"  correlation_id : {correlation_id}\n"
                f"  incident_id    : {(phases[-1]['incident'] or {}).get('incident_id')}\n"
                f"Screenshot THIS incident in the CockroachDB console and the Space,\n"
                f"then drop the files into {run.screenshots.relative_to(REPO_ROOT)}\n"
            )


def _notes(short_id: str, results: dict, phases: list[dict], bedrock_ok: bool) -> str:
    outcome = results.get("outcome", "UNKNOWN")
    mode = "live Bedrock available" if bedrock_ok else "**Bedrock closed at capture — fallback paths used**"
    lines = [
        f"# Chaos run `{short_id}` — {outcome}",
        "",
        f"- correlation id: `{results.get('correlation_id')}`",
        f"- interrupted at step: **{results.get('interrupted_step_index')}**",
        f"- killed pid `{results.get('killed_pid')}` on port `{results.get('killed_port')}`"
        " via `scripts/chaos_kill.py` (real SIGKILL/TerminateProcess, no graceful shutdown)",
        f"- Bedrock at capture time: {mode}",
        f"- final state: `{results.get('final_state')}`",
        f"- steps executed: {results.get('steps_executed')} · duplicated: "
        f"{results.get('duplicated_step_indices') or 'none'}",
        "",
        "## Phases",
        "",
        "| Phase | What the database said |",
        "| --- | --- |",
    ]
    for p in phases:
        lines.append(f"| `{p['phase']}` | {p['note']} — statuses: `{p['step_status_counts']}` |")
    if outcome == "FAIL":
        lines += [
            "",
            "## Why this run failed",
            "",
            f"> {results.get('failure')}",
            "",
            "Kept rather than deleted: a failed capture is a fact about the system, not a mistake to hide.",
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--step-seconds",
        type=float,
        default=8.0,
        help="execution window to strike inside; wide enough that the kill reliably lands mid-step",
    )
    p.add_argument("--keep-logs", action="store_true", help="keep raw uvicorn output, not just the structlog JSON")
    args = p.parse_args()

    if not settings.cockroach_database_url:
        sys.exit("COCKROACH_DATABASE_URL is not set — this capture runs against a live cluster")
    sys.exit(capture_local(args.step_seconds, args.keep_logs))


if __name__ == "__main__":
    main()
