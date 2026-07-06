"""
Unit tests for the recovery-first control flow — the property this whole
project exists to prove (ARCHITECTURE.md §3). These mock MemoryAgent so the
tests assert *ordering and resume semantics* (recovery read before any new
write, interrupted steps re-executed, no duplicate execution) without a live
CockroachDB connection or AWS credentials.
"""
from unittest.mock import MagicMock, patch

import pytest

from agents.orchestrator import handle_alert, lambda_handler

ALERT = {
    "correlation_id": "test-corr-001",
    "service": "checkout-api",
    "region": "us-east-1",
    "severity": "high",
    "text": "Elevated p99 latency on checkout-api",
}


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("agents.orchestrator.time.sleep"):
        yield


def _proposed(action="do_thing"):
    return MagicMock(action=action, rationale="r", based_on_incident_id=None)


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_resumes_at_next_step_after_completed_step(mock_memory, mock_correlation, mock_remediation):
    existing = MagicMock(incident_id="existing-id", state="remediating",
                         last_step_index=1, last_step_status="executed")
    mock_memory.get_open_incident.return_value = existing
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed()

    result = handle_alert(ALERT)

    mock_memory.open_incident.assert_not_called()  # must NOT reopen — the whole point
    assert result["resumed"] is True
    assert result["step_index"] == 2  # last executed (1) + 1


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_reexecutes_step_interrupted_mid_execution(mock_memory, mock_correlation, mock_remediation):
    """The chaos-kill scenario: previous invocation died with step 1 stuck in
    'executing'. The fresh invocation must re-run step 1, not skip to 2 and
    not restart at 0."""
    existing = MagicMock(incident_id="existing-id", state="remediating",
                         last_step_index=1, last_step_status="executing")
    mock_memory.get_open_incident.return_value = existing
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed()

    result = handle_alert(ALERT)

    assert result["step_index"] == 1
    assert result["reexecuted_after_interrupt"] is True
    # The interrupted step is re-run via the resume path of checkpoint_step_start
    # (resuming=True) and then completed — not skipped, not restarted at 0.
    args, kwargs = mock_memory.checkpoint_step_start.call_args
    assert args[0] == "existing-id" and args[1] == 1
    assert kwargs["resuming"] is True
    mock_memory.checkpoint_step_done.assert_called_once_with("existing-id", 1, resolve=False)


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_opens_new_incident_when_none_exists(mock_memory, mock_correlation, mock_remediation):
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed("do_first_thing")

    result = handle_alert(ALERT)

    mock_memory.open_incident.assert_called_once()
    assert result["resumed"] is False
    assert result["step_index"] == 0


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_recovery_read_happens_before_any_write(mock_memory, mock_correlation, mock_remediation):
    """Ordering property: get_open_incident is the FIRST MemoryAgent call."""
    calls = []
    mock_memory.get_open_incident.side_effect = lambda *a, **k: calls.append("read") or None
    mock_memory.open_incident.side_effect = lambda *a, **k: calls.append("write") or "id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed()

    handle_alert(ALERT)

    assert calls[0] == "read"


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_resuming_past_max_steps_closes_loop_without_new_reasoning(mock_memory, mock_correlation, mock_remediation):
    """If every planned step already executed (last_step_index at the max),
    the orchestrator resolves immediately without correlating/proposing
    a step that was never going to run."""
    existing = MagicMock(incident_id="existing-id", state="remediating",
                         last_step_index=2, last_step_status="executed")
    mock_memory.get_open_incident.return_value = existing

    result = handle_alert(ALERT)

    assert result["state"] == "resolved"
    assert result["resumed"] is True
    mock_memory.set_state.assert_called_once_with("existing-id", "resolved")
    mock_correlation.embed.assert_not_called()
    mock_remediation.propose_next_step.assert_not_called()


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_resolves_after_final_step(mock_memory, mock_correlation, mock_remediation):
    """With max_remediation_steps=3, executing step index 2 resolves the incident."""
    existing = MagicMock(incident_id="existing-id", state="remediating",
                         last_step_index=1, last_step_status="executed")
    mock_memory.get_open_incident.return_value = existing
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed()

    result = handle_alert(ALERT)

    assert result["step_index"] == 2
    assert result["state"] == "resolved"
    # Resolution is committed atomically with the final step's completion.
    mock_memory.checkpoint_step_done.assert_called_once_with("existing-id", 2, resolve=True)


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_skips_execution_when_step_already_claimed(mock_memory, mock_correlation, mock_remediation):
    """Concurrency guard: if checkpoint_step_start reports the step was already
    claimed by a racing invocation, this invocation must NOT execute it or
    advance it to 'executed'."""
    existing = MagicMock(incident_id="existing-id", state="remediating",
                         last_step_index=0, last_step_status="executed")
    mock_memory.get_open_incident.return_value = existing
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed()
    mock_memory.checkpoint_step_start.return_value = False

    result = handle_alert(ALERT)

    assert result["skipped_duplicate"] is True
    assert result["step_index"] == 1  # last executed (0) + 1
    mock_memory.checkpoint_step_done.assert_not_called()


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_correlation_failure_does_not_abort_incident(mock_memory, mock_correlation, mock_remediation):
    """Bedrock is best-effort: an embed/vector-search failure must not stop the
    incident from being made durable and driven — remediation simply gets no
    precedents (matches=[])."""
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.side_effect = RuntimeError("bedrock unreachable")
    mock_remediation.propose_next_step.return_value = _proposed()

    result = handle_alert(ALERT)

    assert result["step_index"] == 0
    assert result["state"] in ("remediating", "resolved")
    mock_remediation.propose_next_step.assert_called_once()
    matches_arg = mock_remediation.propose_next_step.call_args[0][0]
    assert matches_arg == []


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_lambda_handler_delegates_to_handle_alert(mock_memory, mock_correlation, mock_remediation):
    """infra/lambda_handler.py re-exports this as the SAM entrypoint."""
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed()

    result = lambda_handler(ALERT, context=None)

    assert result["incident_id"] == "new-id"
