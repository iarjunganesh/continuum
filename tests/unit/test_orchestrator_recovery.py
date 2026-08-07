"""
Unit tests for the recovery-first control flow — the property this whole
project exists to prove (ARCHITECTURE.md §3). These mock MemoryAgent so the
tests assert *ordering and resume semantics* (recovery read before any new
write, interrupted steps re-executed, no duplicate execution) without a live
CockroachDB connection or AWS credentials.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.correlation_agent import CorrelationMatch
from agents.orchestrator import (
    CORRELATION_BEDROCK,
    CORRELATION_UNAVAILABLE,
    PRECEDENT_SUMMARY_CHARS,
    _stack_detail,
    handle_alert,
    lambda_handler,
)
from agents.remediation_agent import (
    SOURCE_BEDROCK,
    SOURCE_PRECEDENT_REPLAY,
    ProposedAction,
)

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


def _proposed(action="do_thing", source=SOURCE_BEDROCK):
    """A real ProposedAction, deliberately not a MagicMock. MagicMock invents
    any attribute you ask it for, so a field added to ProposedAction silently
    becomes a MagicMock here — which is how a non-JSON-serializable value
    reached the `detail` JSONB and failed only against a live cluster. The real
    dataclass forces every new field to be given a real value."""
    return ProposedAction(action=action, rationale="r", based_on_incident_id=None, source=source)


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_resumes_at_next_step_after_completed_step(mock_memory, mock_correlation, mock_remediation):
    existing = MagicMock(incident_id="existing-id", state="remediating", last_step_index=1, last_step_status="executed")
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
    existing = MagicMock(
        incident_id="existing-id", state="remediating", last_step_index=1, last_step_status="executing"
    )
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
    existing = MagicMock(incident_id="existing-id", state="remediating", last_step_index=2, last_step_status="executed")
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
    existing = MagicMock(incident_id="existing-id", state="remediating", last_step_index=1, last_step_status="executed")
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
    existing = MagicMock(incident_id="existing-id", state="remediating", last_step_index=0, last_step_status="executed")
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
    # ...but the degradation must be *recorded*, not silent.
    assert result["correlation_source"] == CORRELATION_UNAVAILABLE


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_live_bedrock_path_is_recorded_in_result_and_step_detail(mock_memory, mock_correlation, mock_remediation):
    """Both Bedrock paths degrade silently by design, so the only way to tell a
    healthy run from a throttled one is this marker. It must reach the caller
    *and* the durable step record — evidence read back from CockroachDB after
    the fact has to be self-describing."""
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed(source=SOURCE_BEDROCK)

    result = handle_alert(ALERT)

    assert result["correlation_source"] == CORRELATION_BEDROCK
    assert result["reasoning_source"] == SOURCE_BEDROCK
    detail = mock_memory.checkpoint_step_start.call_args.kwargs["detail"]
    assert detail["reasoning_source"] == SOURCE_BEDROCK
    assert detail["correlation_source"] == CORRELATION_BEDROCK


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_step_detail_is_json_serializable(mock_memory, mock_correlation, mock_remediation):
    """`detail` is written to a JSONB column, so psycopg dumps it with
    json.dumps. This suite mocks the memory agent and therefore never reaches
    that dump — a non-serializable value in `detail` would sail through here
    and only fail against a live cluster. Assert serializability directly so
    the cheap suite catches it instead of the slow one."""
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed()

    handle_alert(ALERT)

    detail = mock_memory.checkpoint_step_start.call_args.kwargs["detail"]
    json.dumps(detail)  # raises TypeError if any value is not serializable


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_fallback_reasoning_is_recorded_even_when_correlation_succeeded(
    mock_memory, mock_correlation, mock_remediation
):
    """The two sources are independent: the vector search can succeed while
    Claude is throttled. Recording only one would misreport the other."""
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = [MagicMock()]
    mock_remediation.propose_next_step.return_value = _proposed(source=SOURCE_PRECEDENT_REPLAY)

    result = handle_alert(ALERT)

    assert result["correlation_source"] == CORRELATION_BEDROCK
    assert result["reasoning_source"] == SOURCE_PRECEDENT_REPLAY


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_duplicate_claim_result_still_reports_sources(mock_memory, mock_correlation, mock_remediation):
    """The concurrency-skip path returns early — it must not drop the markers,
    or a raced invocation would look like it never touched Bedrock."""
    existing = MagicMock(incident_id="existing-id", state="remediating", last_step_index=0, last_step_status="executed")
    mock_memory.get_open_incident.return_value = existing
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed(source=SOURCE_BEDROCK)
    mock_memory.checkpoint_step_start.return_value = False

    result = handle_alert(ALERT)

    assert result["skipped_duplicate"] is True
    assert result["correlation_source"] == CORRELATION_BEDROCK
    assert result["reasoning_source"] == SOURCE_BEDROCK


def _match(incident_id="prec-1", distance=0.1234, summary="Connection pool saturation on checkout-api"):
    """A real CorrelationMatch — same reasoning as _proposed(): a MagicMock
    would happily return a MagicMock for `.distance`, which round() rejects
    only at runtime and json.dumps rejects only against a live cluster."""
    return CorrelationMatch(incident_id=incident_id, summary=summary, state="resolved", distance=distance)


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_retrieved_precedent_is_persisted_with_the_step(mock_memory, mock_correlation, mock_remediation):
    """`based_on` alone was a bare UUID — it recorded that memory retrieved
    something, not what was recalled or how close it was. The distance is what
    makes the vector search legible as a vector search when read back."""
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = [_match(), _match("prec-2", 0.9)]
    proposed = ProposedAction(action="a", rationale="r", based_on_incident_id="prec-1", source=SOURCE_BEDROCK)
    mock_remediation.propose_next_step.return_value = proposed

    handle_alert(ALERT)

    detail = mock_memory.checkpoint_step_start.call_args.kwargs["detail"]
    assert detail["precedent_distance"] == pytest.approx(0.1234)
    assert detail["precedent_summary"] == "Connection pool saturation on checkout-api"
    assert detail["precedent_state"] == "resolved"
    assert detail["precedents_considered"] == 2
    assert detail["precedent_rank"] == 0
    json.dumps(detail)


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_precedent_detail_describes_the_match_actually_reasoned_from(mock_memory, mock_correlation, mock_remediation):
    """Claude may cite a precedent that isn't the nearest one. Recording
    matches[0] regardless would attach the wrong summary and distance to the
    step — evidence that reads as precise while being wrong."""
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = [
        _match("near", 0.05, "the nearest"),
        _match("cited", 0.42, "the cited one"),
    ]
    mock_remediation.propose_next_step.return_value = ProposedAction(
        action="a", rationale="r", based_on_incident_id="cited", source=SOURCE_BEDROCK
    )

    handle_alert(ALERT)

    detail = mock_memory.checkpoint_step_start.call_args.kwargs["detail"]
    assert detail["precedent_summary"] == "the cited one"
    assert detail["precedent_distance"] == pytest.approx(0.42)
    assert detail["precedent_rank"] == 1


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_no_precedent_writes_no_precedent_fields(mock_memory, mock_correlation, mock_remediation):
    """Absence has to stay meaningful: a step with no precedent and a step whose
    precedent we forgot to record must not look identical."""
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = []
    mock_remediation.propose_next_step.return_value = _proposed()

    handle_alert(ALERT)

    detail = mock_memory.checkpoint_step_start.call_args.kwargs["detail"]
    assert "precedent_distance" not in detail
    assert "precedent_summary" not in detail


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_precedent_summary_is_truncated(mock_memory, mock_correlation, mock_remediation):
    """The step log records enough to recognise the incident, not a second copy
    of the incidents table."""
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = [_match(summary="x" * 500)]
    mock_remediation.propose_next_step.return_value = ProposedAction(
        action="a", rationale="r", based_on_incident_id="prec-1", source=SOURCE_BEDROCK
    )

    handle_alert(ALERT)

    detail = mock_memory.checkpoint_step_start.call_args.kwargs["detail"]
    assert len(detail["precedent_summary"]) == PRECEDENT_SUMMARY_CHARS


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


# ── Stack provenance (_stack_detail) ─────────────────────────────────────────
# These pin what a durable step is allowed to *claim* about the infrastructure
# that produced it. The model ids reach invoke_model and were logged but never
# persisted, so rows could say Bedrock reasoned and never say what reasoned —
# leaving anything downstream to read `settings` at display time, which answers
# "what is configured now", not "what ran then".


def test_runtime_says_lambda_only_when_lambda_says_so(monkeypatch):
    """Read from the runtime's own env var, never inferred from config — a step
    executed on a laptop must not be able to claim it ran in Lambda."""
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert _stack_detail(CORRELATION_BEDROCK, SOURCE_BEDROCK)["runtime"] == "local"

    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "continuum-orchestrator")
    assert _stack_detail(CORRELATION_BEDROCK, SOURCE_BEDROCK)["runtime"] == "lambda"


def test_degraded_step_does_not_inherit_a_model_it_never_called(monkeypatch):
    """Both Bedrock paths degrade silently, so the absence of a model id is the
    only signal that the fallback ran. Recording one anyway would erase it."""
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)

    both = _stack_detail(CORRELATION_BEDROCK, SOURCE_BEDROCK)
    assert both["embedding_model_id"] and both["reasoning_model_id"]
    assert both["bedrock_region"]

    # Bedrock unreachable for correlation, so remediation replayed a precedent:
    # neither model was invoked, so neither may be named.
    degraded = _stack_detail(CORRELATION_UNAVAILABLE, SOURCE_PRECEDENT_REPLAY)
    assert "embedding_model_id" not in degraded
    assert "reasoning_model_id" not in degraded
    assert "bedrock_region" not in degraded
    assert degraded["runtime"] == "local"  # still attestable — it always is

    # Vector search ran, reasoning fell back: exactly one model is nameable.
    partial = _stack_detail(CORRELATION_BEDROCK, SOURCE_PRECEDENT_REPLAY)
    assert "embedding_model_id" in partial
    assert "reasoning_model_id" not in partial


@patch("agents.orchestrator.remediation")
@patch("agents.orchestrator.correlation")
@patch("agents.orchestrator.memory")
def test_step_detail_pins_the_vector_space_of_its_distance(mock_memory, mock_correlation, mock_remediation):
    """`precedent_distance` is only comparable within one embedding model, and
    the corpus has been re-embedded once already — every distance moved from
    ~1.40 to ~0.64. A durable distance without its model is uninterpretable, so
    they must be written together, in the same row."""
    match = CorrelationMatch(incident_id="prec-1", summary="past outage", state="resolved", distance=0.6382)
    mock_memory.get_open_incident.return_value = None
    mock_memory.open_incident.return_value = "new-id"
    mock_correlation.embed.return_value = [0.0] * 8
    mock_correlation.find_similar.return_value = [match]
    mock_remediation.propose_next_step.return_value = ProposedAction(
        action="do_thing", rationale="r", based_on_incident_id="prec-1", source=SOURCE_BEDROCK
    )

    handle_alert(ALERT)

    detail = mock_memory.checkpoint_step_start.call_args.kwargs["detail"]
    assert "precedent_distance" in detail
    assert "embedding_model_id" in detail, "a distance was persisted with no vector space to interpret it in"
