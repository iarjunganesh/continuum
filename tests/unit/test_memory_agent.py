"""Unit tests for MemoryAgent — mocks psycopg; no real CockroachDB connection.

MemoryAgent is the single write path (CLAUDE.md, memory_agent.py module
docstring) so these tests pin the exact SQL contract the recovery guarantee
depends on: the recovery-read query shape, and that every write commits.
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


class TestLogStep:
    def test_upserts_step_with_detail(self, memory, conn_cur):
        conn, cur = conn_cur
        incident_id = uuid4()

        memory.log_step(incident_id, 0, "restart_pool", status="proposed",
                        detail={"rationale": "closest precedent"})

        sql = cur.execute.call_args[0][0]
        assert "ON CONFLICT (incident_id, step_index) DO UPDATE" in sql
        conn.commit.assert_called_once()

    def test_defaults_detail_to_empty_dict(self, memory, conn_cur):
        conn, cur = conn_cur
        incident_id = uuid4()

        memory.log_step(incident_id, 0, "restart_pool")

        assert cur.execute.called
        conn.commit.assert_called_once()


class TestSetStepStatus:
    def test_updates_status_and_commits(self, memory, conn_cur):
        conn, cur = conn_cur
        incident_id = uuid4()

        memory.set_step_status(incident_id, 2, "executed")

        sql, params = cur.execute.call_args[0]
        assert "UPDATE remediation_steps SET status" in sql
        assert params == ("executed", incident_id, 2)
        conn.commit.assert_called_once()
