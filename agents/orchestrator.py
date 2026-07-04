"""
Continuum Orchestrator — Lambda entrypoint.

The ONE rule this module exists to enforce (see ADR 002, ARCHITECTURE.md §3):
on every invocation, before any new reasoning happens, check CockroachDB for
existing open incident state for this alert's correlation_id. If found,
resume from there. Never assume the previous invocation's in-memory state
is available — it isn't, by design.

Each invocation drives exactly ONE remediation step through
propose -> executing -> executed (with a simulated execution window in the
middle — the window scripts/chaos_kill.py strikes in). After
settings.max_remediation_steps executed steps, the incident resolves.
A kill mid-execution leaves status='executing' durably in CockroachDB;
the next cold invocation reads that and re-runs the interrupted step
instead of starting over or double-running completed steps.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from agents.correlation_agent import CorrelationAgent
from agents.memory_agent import MemoryAgent
from agents.remediation_agent import RemediationAgent
from config import settings
from observability.structured_logger import get_logger

log = get_logger(__name__)

memory = MemoryAgent()
correlation = CorrelationAgent()
remediation = RemediationAgent()

_INCOMPLETE = ("proposed", "executing")


def handle_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    alert = {
        "correlation_id": str,
        "service": str,
        "region": str,
        "severity": str,
        "text": str,   # raw alert text, used for embedding
    }
    """
    correlation_id = alert["correlation_id"]

    # --- STEP 1 (mandatory, always first): recovery read ---
    existing = memory.get_open_incident(correlation_id)

    interrupted = False
    if existing:
        incident_id = existing.incident_id
        if existing.last_step_index is not None and existing.last_step_status in _INCOMPLETE:
            # Previous invocation died mid-step — re-run that exact step.
            step_index = existing.last_step_index
            interrupted = True
        else:
            step_index = (existing.last_step_index if existing.last_step_index is not None else -1) + 1
        log.info("resuming_incident", correlation_id=correlation_id, state=existing.state,
                  step_index=step_index, interrupted=interrupted)
    else:
        log.info("new_incident", correlation_id=correlation_id)
        incident_id = memory.open_incident(
            correlation_id=correlation_id,
            service=alert["service"],
            region=alert.get("region", "default"),
            severity=alert["severity"],
            summary=alert["text"][:200],
        )
        memory.set_state(incident_id, "correlating")
        step_index = 0

    # All planned steps already executed -> close the loop.
    if step_index >= settings.max_remediation_steps:
        memory.set_state(incident_id, "resolved")
        return {
            "incident_id": str(incident_id),
            "state": "resolved",
            "steps_executed": step_index,
            "resumed": existing is not None,
        }

    # --- STEP 2: correlate against past incidents ---
    embedding = correlation.embed(alert["text"])
    matches = correlation.find_similar(alert["service"], embedding)

    # --- STEP 3: propose + execute this step, committing every transition ---
    memory.set_state(incident_id, "remediating")
    proposed = remediation.propose_next_step(matches, step_index, alert_text=alert["text"])
    memory.log_step(incident_id, step_index, proposed.action, status="proposed",
                     detail={"rationale": proposed.rationale,
                             "based_on": proposed.based_on_incident_id,
                             "reexecuted_after_interrupt": interrupted})

    memory.set_step_status(incident_id, step_index, "executing")
    # Simulated execution — long enough for chaos_kill.py to strike mid-step.
    time.sleep(settings.step_execution_seconds)
    memory.set_step_status(incident_id, step_index, "executed")

    resolved = step_index >= settings.max_remediation_steps - 1
    if resolved:
        memory.set_state(incident_id, "resolved")

    return {
        "incident_id": str(incident_id),
        "step_index": step_index,
        "action": proposed.action,
        "state": "resolved" if resolved else "remediating",
        "resumed": existing is not None,
        "reexecuted_after_interrupt": interrupted,
    }


def lambda_handler(event, context):
    """AWS Lambda entrypoint — see infra/lambda_handler.py for the deployment wrapper."""
    return handle_alert(event)
