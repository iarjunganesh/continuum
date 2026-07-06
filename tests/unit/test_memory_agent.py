"""Unit tests for MemoryAgent — mocks psycopg; no real CockroachDB connection.

MemoryAgent is the single write path (CLAUDE.md, memory_agent.py module
docstring) so these tests pin the exact SQL contract the recovery guarantee
depends on: the recovery-read query shape, that simple writes commit, and that
the per-step checkpoints run in explicit transactions with the exactly-once
forward-claim (ADR 009).
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from agents.memory_agent import IncidentState, MemoryAgent


@pytest.fixture
def mock_psycopg():
    with patch("agents.memory_agent.psycopg") as mock:
        yield mock


@pytest.fixture
def conn_cur(mock_psycopg):
    conn = MagicMock()
    cur = MagicMock()
    mock_psycopg.connect.return_value.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


@pytest.fixture
def memory(mock_psycopg) -> MemoryAgent:
    return MemoryAgent(dsn="postgresql://mock:mock@localhost:26257/defaultdb")


class TestGetOpenIncident:
    def test_returns_incident_state_when_row_found(self, memory, conn_cur):
        _, cur = conn_cur
        incident_id = uuid4()
        cur.fetchone.return_value = {
            "incident_id": incident_id,
            "correlation_id": "corr-1",
            "service": "checkout-api",
            "state": "remediating",
            "last_step_index": 1,
            "last_step_status": "executing",
        }

        result = memory.get_open_incident("corr-1")

        assert isinstance(result, IncidentState)
        assert result.incident_id == incident_id
        assert result.last_step_index == 1
        assert result.last_step_status == "executing"

    def test_returns_none_when_no_open_incident(self, memory, conn_cur):
        _, cur = conn_cur
        cur.fetchone.return_value = None

        assert memory.get_open_incident("corr-missing") is None

    def test_excludes_resolved_and_escalated_states(self, memory, conn_cur):
        _, cur = conn_cur
        cur.fetchone.return_value = None
        memory.get_open_incident("corr-1")
        sql = cur.execute.call_args[0][0]
        assert "NOT IN ('resolved', 'escalated')" in sql


class TestOpenIncident:
    def test_inserts_and_commits(self, memory, conn_cur):
        conn, cur = conn_cur
        new_id = uuid4()
        cur.fetchone.return_value = (new_id,)

        result = memory.open_incident(
            correlation_id="corr-1", service="checkout-api", region="eu-central-1",
            severity="high", summary="p99 latency spike",
        )

        assert result == new_id
        conn.commit.assert_called_once()
        args = cur.execute.call_args[0][1]
        assert args == ("corr-1", "checkout-api", "eu-central-1", "high", "p99 latency spike")


class TestSetState:
    def test_resolved_sets_resolved_at(self, memory, conn_cur):
        conn, cur = conn_cur
        incident_id = uuid4()

        memory.set_state(incident_id, "resolved")

        sql = cur.execute.call_args[0][0]
        assert "resolved_at = now()" in sql
        conn.commit.assert_called_once()

    def test_non_resolved_state_does_not_touch_resolved_at(self, memory, conn_cur):
        conn, cur = conn_cur
        incident_id = uuid4()

        memory.set_state(incident_id, "remediating")

        sql, params = cur.execute.call_args[0]
        assert "resolved_at" not in sql
        assert params == ("remediating", incident_id)
        conn.commit.assert_called_once()


class TestCheckpointStepStart:
    def test_forward_step_claims_via_on_conflict_do_nothing(self, memory, conn_cur):
        """A brand-new step is claimed with ON CONFLICT DO NOTHING; a single
        affected row means this invocation owns it and the incident advances to
        'remediating' in the same transaction."""
        _, cur = conn_cur
        cur.rowcount = 1
        incident_id = uuid4()

        claimed = memory.checkpoint_step_start(incident_id, 0, "restart_pool",
                                               detail={"rationale": "r"}, resuming=False)

        assert claimed is True
        first_sql = cur.execute.call_args_list[0][0][0]
        assert "ON CONFLICT (incident_id, step_index) DO NOTHING" in first_sql
        # second statement flips the incident to 'remediating'
        second_sql = cur.execute.call_args_list[1][0][0]
        assert "state = 'remediating'" in second_sql

    def test_forward_step_not_claimed_when_row_already_exists(self, memory, conn_cur):
        """If a racing invocation already claimed the step (0 rows affected),
        this returns False and does NOT touch incident state."""
        _, cur = conn_cur
        cur.rowcount = 0
        incident_id = uuid4()

        claimed = memory.checkpoint_step_start(incident_id, 0, "restart_pool", resuming=False)

        assert claimed is False
        assert len(cur.execute.call_args_list) == 1  # only the claim attempt, no incident update

    def test_resume_path_updates_existing_row_and_always_claims(self, memory, conn_cur):
        """Resuming an interrupted step updates the existing row to 'executing'
        (not an INSERT) and always returns True — the re-run is required."""
        _, cur = conn_cur
        incident_id = uuid4()

        claimed = memory.checkpoint_step_start(incident_id, 1, "restart_pool", resuming=True)

        assert claimed is True
        first_sql = cur.execute.call_args_list[0][0][0]
        assert first_sql.strip().startswith("UPDATE remediation_steps SET status = 'executing'")


class TestCheckpointStepDone:
    def test_marks_executed_with_status_guard(self, memory, conn_cur):
        _, cur = conn_cur
        incident_id = uuid4()

        memory.checkpoint_step_done(incident_id, 0, resolve=False)

        sql = cur.execute.call_args_list[0][0][0]
        assert "status = 'executed'" in sql
        assert "AND status = 'executing'" in sql  # the guard against double/out-of-order
        assert len(cur.execute.call_args_list) == 1  # no resolve, so incidents untouched

    def test_resolve_marks_incident_resolved(self, memory, conn_cur):
        _, cur = conn_cur
        incident_id = uuid4()

        memory.checkpoint_step_done(incident_id, 2, resolve=True)

        assert len(cur.execute.call_args_list) == 2
        resolve_sql = cur.execute.call_args_list[1][0][0]
        assert "state = 'resolved'" in resolve_sql
        assert "resolved_at = now()" in resolve_sql
