"""
Drives the synthetic alert stream against the orchestrator — used both for
local development and for driving the recorded demo (submission/DEMO_SCRIPT.md).

Each --tick drives ONE remediation step (propose -> executing -> executed).
Re-running with the same correlation_id resumes the same incident from
CockroachDB until it resolves after settings.max_remediation_steps steps.

Usage:
    python scripts/demo_run.py --tick                  # drive one step
    python scripts/demo_run.py --tick --resume-check   # ...and log whether it resumed
    python scripts/demo_run.py --tick --via-api        # POST to the running API instead
    python scripts/demo_run.py --tick --via-lambda     # invoke the deployed Lambda instead
    python scripts/demo_run.py --tick --new            # start a fresh incident
"""

import argparse
import json
import os
import sys
import uuid

import httpx

# Running as `python scripts/demo_run.py` puts scripts/ (not the repo root)
# on sys.path, so observability won't import otherwise.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observability.structured_logger import get_logger  # noqa: E402

log = get_logger(__name__)

# Shaped like a real Alertmanager payload rather than a sentence someone typed:
# labels, a fired rule name, the query that breached and the telemetry alongside
# it. Vendor-neutral on purpose — the submission rules bar third-party
# trademarks from the recording, and Prometheus/Alertmanager is the one format
# that is both instantly recognisable and nobody's trademark.
#
# The wording is also deliberately NOT a copy of any seeded summary. It used to
# be one, byte for byte, which was invisible while the corpus held hash vectors
# and became obvious the moment it held real Titan ones: identical text embeds
# to an identical vector, so the demo retrieved its precedent at distance
# 0.0000 — a number that demonstrates nothing a string comparison couldn't.
#
# Measured against the committed fixture: retrieves the pool-exhaustion
# precedent at rank 0, d=0.7902, with the runner-up 0.3052 away. It shares no
# prose with that row — no "elevated", no "latency", no "exhaustion" — so the
# match cannot be explained by keyword overlap. Re-measure if this text changes.
DEMO_ALERT = {
    "correlation_id": "demo-incident-001",  # fixed, so re-running proves resume behaviour
    "service": "checkout-api",
    "region": "us-east-1",
    "severity": "high",
    "text": (
        "[FIRING:1] HighLatencyP99 service=checkout-api region=us-east-1 severity=high — "
        "histogram_quantile(0.99, http_server_duration_seconds) = 2.41s exceeds SLO 0.80s for 5m; "
        "db_pool_connections_active 200/200, db_pool_clients_waiting 47"
    ),
}


def tick(resume_check: bool = False, via_api: bool = False, via_lambda: bool = False, new: bool = False):
    alert = dict(DEMO_ALERT)
    if new:
        alert["correlation_id"] = f"demo-incident-{uuid.uuid4().hex[:8]}"

    if via_api:
        # Runs inside the API process — kill THAT process mid-step to demo recovery.
        result = httpx.post("http://localhost:8000/api/v1/alert", json=alert, timeout=60).json()
    elif via_lambda:
        # Invokes the deployed function (docs/DEPLOY.md) — every tick is a real
        # cold-capable Lambda invocation, so the runbook's "a fresh Lambda
        # invocation starts cold" is literal, not simulated.
        import boto3

        from config import settings

        response = boto3.client("lambda", region_name=settings.aws_region).invoke(
            FunctionName=settings.lambda_function_name,
            Payload=json.dumps(alert).encode(),
        )
        result = json.loads(response["Payload"].read())
        if response.get("FunctionError"):
            raise RuntimeError(f"Lambda invocation failed: {result}")
    else:
        from agents.orchestrator import handle_alert

        result = handle_alert(alert)

    print(json.dumps(result, indent=2))
    if resume_check:
        status = "RESUMED from CockroachDB" if result.get("resumed") else "started fresh"
        log.info("demo_tick_result", status=status, **result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tick", action="store_true")
    parser.add_argument("--resume-check", action="store_true")
    parser.add_argument("--via-api", action="store_true")
    parser.add_argument("--via-lambda", action="store_true")
    parser.add_argument("--new", action="store_true")
    args = parser.parse_args()

    if args.tick:
        tick(resume_check=args.resume_check, via_api=args.via_api, via_lambda=args.via_lambda, new=args.new)
    else:
        print("Use --tick to fire a synthetic alert against the orchestrator.")
