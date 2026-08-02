"""
Deployment-restart drill — the last failure mode in the Never-Miss table.

The other suites kill the *process*. This one replaces the *code* underneath a
live incident: an incident is driven into a durable `executing` state on the
deployed function, a real `sam build` + `sam deploy` then swaps the function's
code, and a cold invocation afterwards must resume the interrupted step exactly
once — under a build that did not exist when the step began.

Why it earns its place next to the Lambda-timeout suite rather than duplicating
it: a timeout proves recovery survives the *execution environment* vanishing.
This proves it survives the *deployed artifact changing*, which is the failure
an on-call engineer actually causes — shipping a fix while an incident is open.
The durable `executing` row is the only thing bridging the two versions.

The drill asserts the deployment was real by comparing `CodeSha256` and
`RevisionId` before and after. Without that check a no-op deploy would produce
an identical-looking pass, which is precisely the class of unearned green this
project keeps finding.

Requires a clean checkout to build from (`CodeUri: ../` packages the repo root,
and a working tree with .venv/.mypy_cache blows Lambda's 250 MB limit) and an
admin-ish profile — see docs/DEPLOY.md and `make preflight-deploy`.

Usage:
    python scripts/deploy_restart_drill.py --clone-dir /tmp/continuum-clean
    python scripts/deploy_restart_drill.py --clone-dir ... --profile continuum-admin
    python scripts/deploy_restart_drill.py --clone-dir ... --skip-deploy   # rehearse wiring
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402
from observability.structured_logger import get_logger  # noqa: E402
from scripts.evidence import EvidenceRun  # noqa: E402

log = get_logger(__name__)

# Same reasoning as resilience_bench.LAMBDA_BENCH_SERVICE: a service with no
# seeded embeddings finds no precedent, short-circuits to page_on_call_engineer,
# and never exercises the Bedrock reasoning leg — a cheaper path than production.
DRILL_SERVICE = os.getenv("LAMBDA_BENCH_SERVICE", "checkout-api")
ALERT_TEXT = "checkout-api p99 latency 4200ms, connection pool saturated after deploy"


def _sam() -> str:
    """SAM ships as sam.cmd on Windows, which subprocess won't resolve bare."""
    found = shutil.which("sam") or shutil.which("sam.cmd")
    if not found:
        raise RuntimeError("AWS SAM CLI not found on PATH — see docs/DEPLOY.md")
    return found


def _run(cmd: list[str], cwd: Path, env: dict, label: str) -> str:
    log.info("drill_step_running", step=label, cmd=" ".join(cmd[:3]))
    t = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
    took = time.perf_counter() - t
    if proc.returncode != 0:
        # Both streams: SAM puts build failures on stdout and deploy failures on
        # stderr, and losing whichever half matters wastes a whole build cycle.
        raise RuntimeError(f"{label} failed ({proc.returncode})\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    log.info("drill_step_ok", step=label, seconds=round(took, 1))
    return proc.stdout


def _fn_state(lam, fn: str) -> dict:
    cfg = lam.get_function_configuration(FunctionName=fn)
    return {
        "code_sha256": cfg["CodeSha256"],
        "revision_id": cfg["RevisionId"],
        "last_modified": cfg["LastModified"],
        "version": cfg["Version"],
        "timeout": cfg["Timeout"],
    }


def interrupt_on_lambda(lam, fn: str, correlation_id: str) -> dict:
    """Drive one incident into a durable `executing` row, killed by AWS itself.

    Reuses the Lambda-timeout technique rather than inventing a second kill: the
    function's own Timeout is dropped below the step-execution window, so AWS
    terminates the invocation mid-step with no catchable signal. Restores the
    timeout in a finally — leaving the demo function at 6 s would be a nasty
    surprise during a recording.
    """
    original = lam.get_function_configuration(FunctionName=fn)["Timeout"]
    short = int(max(3, settings.step_execution_seconds + 1))
    alert = {
        "correlation_id": correlation_id,
        "service": DRILL_SERVICE,
        "region": settings.aws_region,
        "severity": "high",
        "text": ALERT_TEXT,
    }
    try:
        lam.update_function_configuration(FunctionName=fn, Timeout=short)
        lam.get_waiter("function_updated_v2").wait(FunctionName=fn)
        resp = lam.invoke(FunctionName=fn, InvocationType="RequestResponse", Payload=json.dumps(alert).encode())
        payload = resp["Payload"].read().decode("utf-8", "replace")
        timed_out = bool("Task timed out" in payload or resp.get("FunctionError"))
    finally:
        lam.update_function_configuration(FunctionName=fn, Timeout=original)
        lam.get_waiter("function_updated_v2").wait(FunctionName=fn)

    return {"timed_out": timed_out, "timeout_used": short, "timeout_restored": original, "alert": alert}


def observe_durable_state(correlation_id: str) -> dict:
    """What CockroachDB holds between the kill and the redeploy — the only
    thing that survives both."""
    with psycopg.connect(settings.cockroach_database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT s.step_index, s.status, count(*) OVER () FROM remediation_steps s "
            "JOIN incidents i USING (incident_id) WHERE i.correlation_id = %s "
            "ORDER BY s.step_index DESC LIMIT 1",
            (correlation_id,),
        )
        row = cur.fetchone()
    if not row:
        return {"step_index": None, "status": None, "steps": 0}
    return {"step_index": row[0], "status": row[1], "steps": row[2]}


def count_rows_for_step(correlation_id: str, step_index: int) -> int:
    with psycopg.connect(settings.cockroach_database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM remediation_steps s JOIN incidents i USING (incident_id) "
            "WHERE i.correlation_id = %s AND s.step_index = %s",
            (correlation_id, step_index),
        )
        return int(cur.fetchone()[0])


def cleanup(correlation_id: str) -> None:
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


def drill(clone_dir: Path, profile: str | None, skip_deploy: bool, keep_rows: bool) -> dict:
    import boto3

    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    lam = session.client("lambda", region_name=settings.aws_region)
    fn = settings.lambda_function_name

    cid = f"resbench-deployrestart-{uuid.uuid4().hex[:8]}"
    result: dict = {"correlation_id": cid, "function": fn, "region": settings.aws_region}

    try:
        result["before"] = _fn_state(lam, fn)

        # 1. Interrupt: AWS kills the invocation mid-step.
        result["interrupt"] = interrupt_on_lambda(lam, fn, cid)
        alert = result["interrupt"].pop("alert")
        result["durable_after_kill"] = observe_durable_state(cid)

        # 2. Redeploy underneath the open incident.
        if skip_deploy:
            result["deploy"] = {"skipped": True}
        else:
            env = dict(os.environ)
            if profile:
                env["AWS_PROFILE"] = profile
            # The template takes the cluster URL as a NoEcho parameter; it is a
            # live credential and never lands in samconfig.toml.
            dsn = settings.cockroach_database_url
            t = time.perf_counter()
            _run([_sam(), "build", "--use-container"], clone_dir, env, "sam build")
            _run(
                [
                    _sam(),
                    "deploy",
                    "--no-confirm-changeset",
                    "--no-fail-on-empty-changeset",
                    "--parameter-overrides",
                    f"CockroachDatabaseUrl={dsn}",
                ],
                clone_dir,
                env,
                "sam deploy",
            )
            result["deploy"] = {"skipped": False, "seconds": round(time.perf_counter() - t, 1)}

        result["after"] = _fn_state(lam, fn)
        # Did a deployment actually happen? A no-op deploy would otherwise pass
        # while proving nothing about surviving a code swap.
        result["code_replaced"] = result["before"]["code_sha256"] != result["after"]["code_sha256"]
        result["revision_changed"] = result["before"]["revision_id"] != result["after"]["revision_id"]

        # 3. Recover on the NEW build, cold.
        t = time.perf_counter()
        resp = lam.invoke(FunctionName=fn, InvocationType="RequestResponse", Payload=json.dumps(alert).encode())
        payload = json.loads(resp["Payload"].read().decode("utf-8", "replace"))
        result["resume_ms"] = round((time.perf_counter() - t) * 1000.0, 1)
        result["recovery_payload"] = payload

        step_index = payload.get("step_index")
        result["resumed"] = bool(payload.get("reexecuted_after_interrupt"))
        result["same_incident"] = payload.get("incident_id") is not None
        result["rows_for_step"] = count_rows_for_step(cid, step_index) if step_index is not None else None
        result["duplicated"] = bool(result["rows_for_step"] not in (None, 1))
        result["passed"] = bool(
            result["interrupt"]["timed_out"]
            and result["durable_after_kill"]["status"] == "executing"
            and result["resumed"]
            and not result["duplicated"]
            and (skip_deploy or result["code_replaced"] or result["revision_changed"])
        )
    finally:
        if not keep_rows:
            cleanup(cid)

    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clone-dir", required=True, help="clean checkout to build from (never the working tree)")
    ap.add_argument("--profile", default=os.getenv("AWS_PROFILE"), help="admin-ish AWS profile for CloudFormation")
    ap.add_argument("--skip-deploy", action="store_true", help="rehearse the wiring without redeploying")
    ap.add_argument("--keep-rows", action="store_true", help="leave the drill's incident in the cluster")
    args = ap.parse_args()

    clone = Path(args.clone_dir).resolve()
    if not (clone / "infra" / "template.yaml").exists():
        raise SystemExit(f"{clone} does not look like a Continuum checkout (no infra/template.yaml)")

    # Its own evidence kind, not a `resilience` run: this drill produces one
    # suite, and dropping a single-suite folder into assets/resilience-run/
    # makes it the newest run for `make charts` and the console panel, both of
    # which would then find none of the suites they render.
    run = EvidenceRun("deploy-restart")
    out = drill(clone, args.profile, args.skip_deploy, args.keep_rows)
    run.write_json("deploy-restart", out)
    run.finalize({"deploy_restart_passed": out.get("passed")})

    print(json.dumps(out, indent=2, default=str))
    print(f"\nevidence: {run.dir}")
    raise SystemExit(0 if out.get("passed") else 1)
