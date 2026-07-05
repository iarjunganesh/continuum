"""
Drives the synthetic alert stream against the orchestrator — used both for
local development and for driving the recorded demo (docs/DEMO_RUNBOOK.md).

Each --tick drives ONE remediation step (propose -> executing -> executed).
Re-running with the same correlation_id resumes the same incident from
CockroachDB until it resolves after settings.max_remediation_steps steps.

Usage:
    python scripts/demo_run.py --tick                  # drive one step
    python scripts/demo_run.py --tick --resume-check   # ...and log whether it resumed
    python scripts/demo_run.py --tick --via-api        # POST to the running API instead
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

DEMO_ALERT = {
    "correlation_id": "demo-incident-001",  # fixed, so re-running proves resume behaviour
    "service": "checkout-api",
    "region": "us-east-1",
    "severity": "high",
    "text": "Elevated p99 latency on checkout-api in us-east-1, likely connection pool exhaustion",
}


def tick(resume_check: bool = False, via_api: bool = False, new: bool = False):
    alert = dict(DEMO_ALERT)
    if new:
        alert["correlation_id"] = f"demo-incident-{uuid.uuid4().hex[:8]}"

    if via_api:
        # Runs inside the API process — kill THAT process mid-step to demo recovery.
        result = httpx.post("http://localhost:8000/api/v1/alert", json=alert, timeout=60).json()
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
    parser.add_argument("--new", action="store_true")
    args = parser.parse_args()

    if args.tick:
        tick(resume_check=args.resume_check, via_api=args.via_api, new=args.new)
    else:
        print("Use --tick to fire a synthetic alert against the orchestrator.")
