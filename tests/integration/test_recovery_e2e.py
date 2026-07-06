"""
Integration test — requires a real CockroachDB instance at
COCKROACH_DATABASE_URL. Exercises the full kill-and-recover flow end to end
against the real schema (infra/schema.sql) and the real recovery-read SQL in
memory_agent.py — the same sequence used in the demo video.

Correlation/Remediation agents are patched to avoid needing AWS credentials
in CI; that boundary (Bedrock reachability) is already covered by the mocked
unit suite. What this test proves that the unit suite cannot: the schema
actually accepts these writes, and get_open_incident's recovery query
actually returns the right row from a real CockroachDB instance under
concurrent-invocation semantics, not a MagicMock standing in for one.

Run explicitly against a test cluster:
    COCKROACH_DATABASE_URL=... STEP_EXECUTION_SECONDS=0 pytest tests/integration -v
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

import psycopg
import pytest

from config import settings

pytestmark = pytest.mark.skipif(
    "COCKROACH_DATABASE_URL" not in os.environ,
    reason="requires a live CockroachDB instance — set COCKROACH_DATABASE_URL to run",
)


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


def _alert(correlation_id: str) -> dict:
    return {
        "correlation_id": correlation_id,
        "service": "checkout-api",
        "region": "eu-central-1",
        "severity": "high",
        "text": "Elevated p99 latency on checkout-api (integration test)",
    }


def _proposed(action="do_thing"):
    return MagicMock(action=action, rationale="integration test rationale", based_on_incident_id=None)


@pytest.fixture(autouse=True)
def no_external_calls():
    """Correlation/Remediation stay mocked — this test isolates the
    CockroachDB recovery contract, not Bedrock reachability."""
    with patch("agents.orchestrator.correlation") as mock_correlation, \
         patch("agents.orchestrator.remediation") as mock_remediation:
        mock_correlation.embed.return_value = [0.0] * 8
        mock_correlation.find_similar.return_value = []
        mock_remediation.propose_next_step.return_value = _proposed()
        yield


def test_full_recovery_cycle(correlation_id):
    from agents.orchestrator import handle_alert

    alert = _alert(correlation_id)

    # 1. First invocation opens a new incident and executes step 0 for real
    #    against CockroachDB — proves the schema (UUID PK, JSONB detail,
    #    CHECK constraints) accepts real writes, not mocked ones.
    first = handle_alert(alert)
    assert first["resumed"] is False
    assert first["step_index"] == 0
    incident_id = first["incident_id"]

    # 2. Simulate a hard kill: this is the exact durable state a real
    #    chaos_kill.py strike leaves — step 0 committed as 'executing' and
    #    never advanced to 'executed'. We force it directly rather than
    #    literally killing a subprocess, because what's under test here is
    #    whether the *next* invocation reads this state correctly from a
    #    real cluster, not whether OS process termination works.
    with psycopg.connect(os.environ["COCKROACH_DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE remediation_steps SET status = 'executing' "
            "WHERE incident_id = %s AND step_index = 0",
            (incident_id,),
        )
        conn.commit()

    # 3. A fresh call with no shared Python state (module-level `memory` is
    #    the same MemoryAgent instance, but it opens a new connection per
    #    call — see memory_agent.py — so this exercises the real recovery
    #    read, not warm process memory).
    second = handle_alert(alert)
    assert second["resumed"] is True
    assert second["step_index"] == 0, "must re-run the interrupted step, not skip to step 1"
    assert second["reexecuted_after_interrupt"] is True

    # 4. Drive the remaining steps to resolution against the real cluster.
    result = second
    while result["state"] != "resolved":
        result = handle_alert(alert)
    assert result["state"] == "resolved"

    with psycopg.connect(os.environ["COCKROACH_DATABASE_URL"]) as conn, \
         conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM remediation_steps WHERE incident_id = %s AND status = 'executed'",
            (incident_id,),
        )
        executed_count = cur.fetchone()[0]
    assert executed_count == settings.max_remediation_steps, (
        "each step_index must appear exactly once as 'executed' — "
        "no duplicate execution, no skipped step"
    )


def test_forward_step_claim_is_exactly_once(correlation_id):
    """The concurrency guard proven against a real cluster: two invocations
    racing to claim the SAME new step — only one may win. We invoke the claim
    twice directly (deterministic, no thread-scheduling flakiness); the second
    must return False so the orchestrator skips it, and the cluster must hold
    exactly one row for that step_index — never a duplicate.
    """
    from agents.memory_agent import MemoryAgent

    memory = MemoryAgent()
    incident_id = memory.open_incident(
        correlation_id=correlation_id, service="checkout-api",
        region="eu-central-1", severity="high", summary="claim test",
    )

    first = memory.checkpoint_step_start(incident_id, 0, "restart_pool", resuming=False)
    second = memory.checkpoint_step_start(incident_id, 0, "restart_pool", resuming=False)

    assert first is True, "first invocation must claim the new step"
    assert second is False, "second invocation must be refused — no duplicate claim"

    with psycopg.connect(os.environ["COCKROACH_DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM remediation_steps WHERE incident_id = %s AND step_index = 0",
            (incident_id,),
        )
        assert cur.fetchone()[0] == 1, "the racing claim must not create a second row"
