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

`--via-lambda` runs the same three phases against the **deployed** function, and
lets **AWS** deliver the kill: the function's own timeout is lowered below its
step-execution window, so Lambda terminates the invocation mid-step with no
catchable signal and no opportunity to checkpoint. The resume is another cold
invocation of the same function. That is the `chaos-run/lambda-<id>` half of the
plan in `assets/README.md` — the contract holding across *invocations* rather
than across process restarts, which is what makes the statelessness claim
literal instead of simulated.

Usage:
    python scripts/chaos_capture.py                  # local process kill
    python scripts/chaos_capture.py --keep-logs      # keep raw uvicorn output too
    python scripts/chaos_capture.py --pause          # HOLD at the frozen phase for screenshots
    python scripts/chaos_capture.py --via-lambda --profile continuum-admin

`--pause` is the only way to photograph the `executing` row. Without it the run
resolves in the same breath, and afterwards the console shows `resolved` — the
interrupted state is not reproducible after the fact. Use it for any run whose
screenshots or video footage you intend to keep.

`--via-lambda` needs `lambda:UpdateFunctionConfiguration`, so it needs the
**admin** profile — the default `continuum-bedrock` identity is Bedrock-invoke
only by design. Pass `--profile continuum-admin` and unset
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` first: static keys in the
environment outrank a profile in boto3's own resolution order, which is why that
misconfiguration arrives as an IAM `AccessDenied` rather than a config error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
# AWS helpers — only used by --via-lambda
# --------------------------------------------------------------------------
_DSN_IN_TEXT = re.compile(r"postgres(?:ql)?://[^\s\"']+")


def _mask_account(text: str) -> str:
    """Replace a 12-digit AWS account id with a placeholder.

    Manifests are committed. `scripts/redact_evidence.py` masks the account id
    out of console *screenshots* for the same reason; an ARN written into JSON
    would walk straight past that.
    """
    return re.sub(r"\b\d{12}\b", "<account-id>", text)


def _redact(text: str) -> str:
    """Strip anything DSN-shaped out of captured log text before it is written.

    The function's own logs should never carry a connection string — but a
    psycopg exception trace can, and this file's output is committed to a public
    repository. A secret in scrollback is a secret to rotate; a secret in git is
    worse. See the "never print a secret" rule in `CLAUDE.md`.
    """
    return _DSN_IN_TEXT.sub("postgresql://<redacted>", text)


def _aws_session(profile: str | None):
    """A boto3 session, pinned to an explicit profile when one is named.

    Naming the profile explicitly matters: botocore drops the environment
    credential provider from the chain when `profile_name` is passed, which is
    the one reliable way to stop `.env`'s static Bedrock-only keys from
    outranking the admin profile.
    """
    import boto3

    return boto3.Session(profile_name=profile) if profile else boto3.Session()


def _caller_identity(session) -> str:
    try:
        return _mask_account(session.client("sts", region_name=settings.aws_region).get_caller_identity()["Arn"])
    except Exception as exc:  # noqa: BLE001 — provenance is best-effort
        return f"(unavailable: {exc!r})"


def _fetch_function_logs(session, function_name: str, start_ms: int) -> str:
    """The function's own CloudWatch log for the capture window.

    This is the Lambda run's equivalent of the local run's uvicorn log: the
    invocation's account of what it did, written by AWS rather than by us. Both
    `INIT_START` (a cold environment) and `recovered_incident_state` (the
    recovery read) land here, which is precisely the pair the claim rests on.

    Best-effort by design — the capture's assertions are made against durable
    CockroachDB rows, so a missing `logs:FilterLogEvents` permission must not
    fail a run that otherwise proved everything it set out to.
    """
    try:
        logs = session.client("logs", region_name=settings.aws_region)
        paginator = logs.get_paginator("filter_log_events")
        lines: list[str] = []
        for page in paginator.paginate(
            logGroupName=f"/aws/lambda/{function_name}",
            startTime=start_ms,
        ):
            for event in page.get("events", []):
                lines.append(event["message"].rstrip("\n"))
        return _redact("\n".join(lines)) + "\n"
    except Exception as exc:  # noqa: BLE001
        return f"(log fetch failed: {exc!r})\n"


def _discard_attempt(correlation_id: str) -> None:
    """Delete the rows an abandoned calibration attempt left behind.

    Only ever called for an attempt whose timeout missed the execution window,
    so it never touches the run being captured. Deleting rather than leaving
    them: `docs/CLUSTER_OPS.md` exists because an earlier bench left hundreds of
    incidents frozen in `remediating` on the cluster judges open.
    """
    try:
        with psycopg.connect(settings.cockroach_database_url) as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM remediation_steps WHERE incident_id IN "
                "(SELECT incident_id FROM incidents WHERE correlation_id = %s)",
                (correlation_id,),
            )
            cur.execute(
                "DELETE FROM incident_embeddings WHERE incident_id IN "
                "(SELECT incident_id FROM incidents WHERE correlation_id = %s)",
                (correlation_id,),
            )
            cur.execute("DELETE FROM incidents WHERE correlation_id = %s", (correlation_id,))
            conn.commit()
    except Exception as exc:  # noqa: BLE001 — tidy-up must never mask the real outcome
        log.warning("discard_attempt_failed", correlation_id=correlation_id, error=repr(exc))


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------
def _pause_for_screenshots(correlation_id: str, incident_id: str | None) -> None:
    """Hold the frozen state on the cluster until the operator says go.

    This exists because `assets/chaos-run/README.md` instructs the operator to
    screenshot the `executing` row "while the run is paused at step [4/6]" — and
    for a long time nothing paused. The print landed microseconds before the
    resuming process started, so the one screenshot that carries the argument
    was impossible to take, and every `screenshots/` folder stayed empty.

    The frozen row is not reproducible after the fact: once the run resolves, the
    console shows `resolved` and the interrupted state is gone forever. Pausing
    here is the ONLY window in which that screenshot exists.
    """
    print("\n" + "=" * 72)
    print("  PAUSED — the step is frozen in 'executing' and NO process owns it.")
    print("  This state does not exist before this moment or after you continue.")
    print("")
    print(f"  correlation_id : {correlation_id}")
    if incident_id:
        print(f"  incident_id    : {incident_id}")
    print("")
    print("  Capture now:")
    print("    1. CockroachDB console -> SQL shell:")
    print("       SELECT step_index, status, action FROM remediation_steps")
    print(f"       WHERE incident_id = '{incident_id or '<see above>'}' ORDER BY step_index;")
    print("    2. The Gradio console timeline showing the step mid-flight")
    print("    3. If recording: this is video beat 7 — hold the frame 3+ seconds")
    print("")
    print("  Save into the run's screenshots/ folder, prefixed with the run id.")
    print("=" * 72)
    try:
        input("\n  Press ENTER to resume (the cold process picks up this exact step)... ")
    except EOFError:
        # Non-interactive (CI, piped stdin): never block a scripted run.
        print("  [no tty — continuing without pausing]")


def capture_local(step_seconds: float, keep_logs: bool, pause: bool = False) -> int:
    run = new_run("chaos", label="local")
    correlation_id = f"chaos-{uuid.uuid4().hex[:8]}"
    memory = MemoryAgent()
    alert = {
        "correlation_id": correlation_id,
        "service": SERVICE,
        "region": REGION,
        "severity": "high",
        # Alertmanager-shaped and vendor-neutral, matching demo_run.DEMO_ALERT —
        # this text becomes the incident summary a judge reads in the CockroachDB
        # Cloud console screenshot, so it should look like something a monitor
        # emitted. Measured against the committed fixture: retrieves the
        # pool-exhaustion precedent at rank 0, d=0.8313, runner-up 0.2768 away.
        # Deliberately not a copy of any seeded summary — see the note on
        # DEMO_ALERT for why identical text used to return distance 0.0000.
        "text": (
            "[FIRING:1] HighLatencyP99 service=checkout-api region=eu-central-1 severity=high — "
            "histogram_quantile(0.99, http_server_duration_seconds) = 3.08s exceeds SLO 0.80s for 5m; "
            "db_pool_connections_active 200/200, db_pool_clients_waiting 63, deploy_age_minutes 12"
        ),
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
        print("[4/6] CAPTURED: step frozen in 'executing' with no live process")
        if pause:
            _pause_for_screenshots(
                correlation_id, frozen["incident"].get("incident_id") if frozen.get("incident") else None
            )

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


def capture_lambda(pause: bool, profile: str | None, max_attempts: int = 4) -> int:
    """The same three phases, with AWS delivering the kill.

    Nothing here simulates a failure. The function's timeout is lowered below
    its own step-execution window, so the invocation is terminated by Lambda
    mid-step — no signal the runtime can catch, no cleanup, no checkpoint. The
    resume is a second cold invocation of the same function, and every assertion
    is made against rows read back out of CockroachDB rather than against a
    return value.
    """
    import time as _time

    run = new_run("chaos", label="lambda")
    memory = MemoryAgent()
    session = _aws_session(profile)
    lam = session.client("lambda", region_name=settings.aws_region)
    fn = settings.lambda_function_name
    started_ms = int(_time.time() * 1000) - 5_000  # a little slack for clock skew

    phases: list[dict] = []
    results: dict = {
        "mode": "aws-lambda-timeout",
        "function": fn,
        "aws_region": settings.aws_region,
        "caller_identity": _caller_identity(session),
        "calibration_attempts": [],
    }
    correlation_id = ""
    original_timeout: int | None = None

    print(f"\n=== chaos capture {run.short_id} (via Lambda) · function={fn} ===\n")
    print(f"      identity: {results['caller_identity']}")

    probe_out, bedrock_ok = _probe_bedrock()
    run.write_text("bedrock-probe.txt", probe_out)
    results["bedrock_reachable_at_capture"] = bedrock_ok
    print(f"[0/6] bedrock probe: {'OK — live path available' if bedrock_ok else 'CLOSED — run will use fallbacks'}")

    def _alert(cid: str) -> dict:
        return {
            "correlation_id": cid,
            "service": SERVICE,
            "region": REGION,
            "severity": "high",
            # Same text as the local capture, deliberately: the two runs prove
            # the same contract in two execution environments, and a judge
            # comparing them should be comparing the environment, not the input.
            "text": (
                "[FIRING:1] HighLatencyP99 service=checkout-api region=eu-central-1 severity=high — "
                "histogram_quantile(0.99, http_server_duration_seconds) = 3.08s exceeds SLO 0.80s for 5m; "
                "db_pool_connections_active 200/200, db_pool_clients_waiting 63, deploy_age_minutes 12"
            ),
        }

    def _wait_updated() -> None:
        lam.get_waiter("function_updated_v2").wait(FunctionName=fn)

    def _invoke(cid: str) -> dict:
        resp = lam.invoke(FunctionName=fn, InvocationType="RequestResponse", Payload=json.dumps(_alert(cid)).encode())
        raw = resp["Payload"].read().decode("utf-8", "replace")
        return {"function_error": resp.get("FunctionError"), "raw": raw}

    try:
        # Narrow reads only. `get_function_configuration()` returns the whole
        # environment, and this function's environment holds the live cluster
        # DSN with its password — so the response is picked apart field by field
        # and never logged, printed, or written wholesale (see `CLAUDE.md`).
        conf = lam.get_function_configuration(FunctionName=fn)
        original_timeout = conf["Timeout"]
        results["original_timeout"] = original_timeout
        # Which build produced this evidence. Without it the run says "the
        # deployed function recovered" while being silent about *which* function
        # that was — and the function has gone five days stale before.
        results["function_build"] = {
            "code_sha256": conf.get("CodeSha256"),
            "last_modified": conf.get("LastModified"),
            "runtime": conf.get("Runtime"),
            "memory_size_mb": conf.get("MemorySize"),
            "version": conf.get("Version"),
        }
        print(f"[1/6] function timeout is {original_timeout}s — lowering it so AWS kills the step mid-flight")
        print(f"      build: CodeSha256={conf.get('CodeSha256')} last modified {conf.get('LastModified')}")

        # --- calibrate: land the kill INSIDE the execution window ----------
        # Too short and Lambda kills before `checkpoint_step_start` commits, so
        # nothing is durable and there is nothing to resume — a weaker result
        # that must not be presented as the real one. Too long and the step
        # completes. Both outcomes are recorded rather than retried silently.
        timeout = int(max(3, settings.step_execution_seconds + 1))
        interrupted_at: int | None = None
        invoke_result: dict = {}

        for attempt in range(1, max_attempts + 1):
            correlation_id = f"chaos-lambda-{uuid.uuid4().hex[:8]}"
            lam.update_function_configuration(FunctionName=fn, Timeout=timeout)
            _wait_updated()
            print(f"      attempt {attempt}: timeout={timeout}s  correlation_id={correlation_id}")

            box: dict = {}

            def _fire(cid: str = correlation_id, sink: dict = box) -> None:
                try:
                    sink.update(_invoke(cid))
                except Exception as exc:  # noqa: BLE001 — recorded, never fatal here
                    sink["error"] = repr(exc)

            thread = threading.Thread(target=_fire, daemon=True)
            thread.start()

            # Poll for the step to become durably `executing` while the
            # invocation is still in flight. This is phase 01: the step is
            # committed and something is still alive to own it.
            deadline = _time.time() + timeout + 60
            seen = None
            while _time.time() < deadline:
                st = memory.get_open_incident(correlation_id)
                if st is not None and st.last_step_status == "executing":
                    seen = st.last_step_index
                    break
                if not thread.is_alive() and st is None:
                    break
                _time.sleep(0.2)

            if seen is not None and thread.is_alive():
                phases.append(
                    snapshot(correlation_id, "01-before-kill", f"step {seen} executing; invocation in flight")
                )
            thread.join(timeout=timeout + 90)
            outcome = {
                "attempt": attempt,
                "timeout": timeout,
                "correlation_id": correlation_id,
                "durable_executing_step": seen,
                "function_error": box.get("function_error"),
                "timed_out": "Task timed out" in str(box.get("raw", "")) or bool(box.get("function_error")),
            }
            results["calibration_attempts"].append(outcome)

            if outcome["timed_out"] and seen is not None:
                interrupted_at = seen
                invoke_result = box
                break

            # Not usable — say why, discard the rows, and adjust.
            if not outcome["timed_out"]:
                print("      → invocation completed; timeout too generous, tightening")
                timeout = max(3, timeout - 1)
            else:
                print("      → AWS killed it before the step was durable; widening")
                timeout += 2
            phases = [p for p in phases if p["phase"] != "01-before-kill"]
            _discard_attempt(correlation_id)

        if interrupted_at is None:
            raise CaptureFailed(
                f"no attempt landed the timeout inside the execution window after {max_attempts} tries; "
                f"see calibration_attempts in the manifest"
            )

        results["correlation_id"] = correlation_id
        results["interrupted_step_index"] = interrupted_at
        results["timeout_used"] = timeout
        results["kill_delivered_by"] = "AWS Lambda (function timeout)"
        results["timeout_payload"] = _redact(str(invoke_result.get("raw", ""))[:2000])
        print(f"[2/6] step {interrupted_at} is durably 'executing' in CockroachDB")
        print(f"[3/6] AWS terminated the invocation mid-step (timeout {timeout}s) — no catchable signal")

        # --- the money shot ------------------------------------------------
        frozen = snapshot(
            correlation_id,
            "02-frozen",
            "invocation terminated by AWS; interrupted step still 'executing' in CockroachDB",
        )
        phases.append(frozen)
        frozen_step = next((s for s in frozen["remediation_steps"] if s["step_index"] == interrupted_at), None)
        if frozen_step is None or frozen_step["status"] != "executing":
            raise CaptureFailed(f"interrupted step is not 'executing' after the timeout: {frozen_step}")
        print("[4/6] CAPTURED: step frozen in 'executing' with no invocation alive to own it")
        if pause:
            _pause_for_screenshots(
                correlation_id, frozen["incident"].get("incident_id") if frozen.get("incident") else None
            )

        # --- resume, on the same function, cold ----------------------------
        # The timeout goes back FIRST: a resume invocation under the shortened
        # timeout would be killed too, and would prove nothing about recovery.
        lam.update_function_configuration(FunctionName=fn, Timeout=original_timeout)
        _wait_updated()

        resumed = json.loads(_invoke(correlation_id)["raw"])
        results["resume_response"] = resumed
        if not resumed.get("resumed"):
            raise CaptureFailed(f"cold invocation did not report a resume: {resumed}")
        if resumed.get("step_index") != interrupted_at:
            raise CaptureFailed(f"resumed at step {resumed.get('step_index')}, expected {interrupted_at}")
        if not resumed.get("reexecuted_after_interrupt"):
            raise CaptureFailed("resume did not re-execute the interrupted step")
        print(f"[5/6] a cold invocation resumed at step {interrupted_at} — the exact step AWS killed")

        state = resumed.get("state")
        guard = 0
        while state != "resolved" and guard < settings.max_remediation_steps + 3:
            state = json.loads(_invoke(correlation_id)["raw"]).get("state")
            guard += 1

        after = snapshot(correlation_id, "03-after-resume", "incident resolved; every step executed exactly once")
        phases.append(after)

        indices = [s["step_index"] for s in after["remediation_steps"]]
        duplicated = sorted({i for i in indices if indices.count(i) > 1})
        executed = [s for s in after["remediation_steps"] if s["status"] == "executed"]
        # `runtime` is written from the function's own AWS_LAMBDA_FUNCTION_NAME
        # and never from config, so it is the durable row's own attestation that
        # this ran in Lambda — the one claim a local capture cannot make.
        runtimes = sorted({(s.get("detail") or {}).get("runtime") for s in after["remediation_steps"]})
        results.update(
            {
                "final_state": after["incident"]["state"] if after["incident"] else None,
                "steps_executed": len(executed),
                "duplicated_step_indices": duplicated,
                "step_runtimes": runtimes,
                "exactly_once": not duplicated and len(executed) == settings.max_remediation_steps,
            }
        )
        if duplicated:
            raise CaptureFailed(f"step(s) executed more than once: {duplicated} — exactly-once violated")
        if len(executed) != settings.max_remediation_steps:
            raise CaptureFailed(f"expected {settings.max_remediation_steps} executed steps, found {len(executed)}")
        if "lambda" not in runtimes:
            raise CaptureFailed(f"no step recorded runtime 'lambda' — this did not run on the function: {runtimes}")
        print(f"[6/6] resolved · {len(executed)} steps executed · 0 duplicated · runtime {runtimes}")
        results["outcome"] = "PASS"
        return 0

    except CaptureFailed as exc:
        results["outcome"] = "FAIL"
        results["failure"] = str(exc)
        print(f"\nCAPTURE FAILED: {exc}\n", file=sys.stderr)
        return 1
    finally:
        # Leaving the demo function on a 6-second timeout would be a nasty
        # surprise days later, so this restore is unconditional.
        if original_timeout is not None:
            try:
                lam.update_function_configuration(FunctionName=fn, Timeout=original_timeout)
                _wait_updated()
                results["timeout_restored"] = original_timeout
            except Exception as exc:  # noqa: BLE001
                results["timeout_restored"] = f"FAILED: {exc!r}"
                print(
                    f"WARNING: could not restore the function timeout to {original_timeout}s: {exc!r}", file=sys.stderr
                )
        run.write_text("cloudwatch-log.txt", _fetch_function_logs(session, fn, started_ms))
        for p in phases:
            run.write_json(f"{p['phase']}.json", p)
        run.write_json("remediation-steps.json", {"correlation_id": correlation_id, "phases": phases})
        run.write_json("session-metadata.json", results)
        run.write_text("NOTES.md", _notes(run.short_id, results, phases, bedrock_ok))
        manifest = run.finalize(extra=results)
        print(f"\nevidence: {run.dir.relative_to(REPO_ROOT)}")
        print(f"manifest: {manifest.relative_to(REPO_ROOT)}")
        if results.get("outcome") == "PASS":
            print(
                f"\nThe incident is LEFT IN THE CLUSTER on purpose.\n"
                f"  correlation_id : {correlation_id}\n"
                f"  incident_id    : {(phases[-1]['incident'] or {}).get('incident_id')}\n"
                f"Screenshot THIS incident in the CockroachDB console and CloudWatch,\n"
                f"then drop the files into {run.screenshots.relative_to(REPO_ROOT)}\n"
            )


def _notes(short_id: str, results: dict, phases: list[dict], bedrock_ok: bool) -> str:
    outcome = results.get("outcome", "UNKNOWN")
    mode = "live Bedrock available" if bedrock_ok else "**Bedrock closed at capture — fallback paths used**"
    if results.get("mode") == "aws-lambda-timeout":
        how = (
            f"- killed by **AWS**: the `{results.get('function')}` function's timeout was lowered to "
            f"`{results.get('timeout_used')}s` (from `{results.get('original_timeout')}s`, restored afterwards), so "
            "Lambda terminated the invocation mid-step — no catchable signal, no cleanup, no checkpoint"
        )
        extra = [
            "- resumed by a **second cold invocation of the same function**, not by a local process",
            f"- durable steps recorded runtime: `{results.get('step_runtimes')}` — read from the function's own "
            "`AWS_LAMBDA_FUNCTION_NAME`, never from config",
        ]
    else:
        how = (
            f"- killed pid `{results.get('killed_pid')}` on port `{results.get('killed_port')}`"
            " via `scripts/chaos_kill.py` (real SIGKILL/TerminateProcess, no graceful shutdown)"
        )
        extra = []
    lines = [
        f"# Chaos run `{short_id}` — {outcome}",
        "",
        f"- correlation id: `{results.get('correlation_id')}`",
        f"- interrupted at step: **{results.get('interrupted_step_index')}**",
        how,
        *extra,
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
    p.add_argument(
        "--pause",
        action="store_true",
        help=(
            "hold at phase [4/6] — the step frozen in 'executing' with no live process — until ENTER. "
            "The ONLY window in which that screenshot exists; the state is gone once the run resolves"
        ),
    )
    p.add_argument(
        "--via-lambda",
        action="store_true",
        help=(
            "capture against the DEPLOYED function and let AWS deliver the kill (a function timeout "
            "lowered below the step window). Needs lambda:UpdateFunctionConfiguration — use --profile"
        ),
    )
    p.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE"),
        help=(
            "AWS profile for --via-lambda (e.g. continuum-admin). Naming it explicitly removes the "
            "environment credential provider from boto3's chain, so .env's Bedrock-only static keys "
            "cannot silently outrank it"
        ),
    )
    args = p.parse_args()

    if not settings.cockroach_database_url:
        sys.exit("COCKROACH_DATABASE_URL is not set — this capture runs against a live cluster")
    if args.via_lambda:
        sys.exit(capture_lambda(args.pause, args.profile))
    sys.exit(capture_local(args.step_seconds, args.keep_logs, args.pause))


if __name__ == "__main__":
    main()
