"""Unit tests for RemediationAgent — mocks boto3 (Bedrock Converse API).
Covers the three propose_next_step paths: no precedent, successful Bedrock
reasoning, and the deterministic fallback when Bedrock is unreachable."""

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.correlation_agent import CorrelationMatch
from agents.remediation_agent import (
    SOURCE_BEDROCK,
    SOURCE_NO_PRECEDENT,
    SOURCE_PRECEDENT_REPLAY,
    RemediationAgent,
)


@pytest.fixture
def agent() -> RemediationAgent:
    return RemediationAgent()


def _bedrock_response(action: str, rationale: str, fenced: bool = False) -> dict:
    text = json.dumps({"action": action, "rationale": rationale})
    if fenced:
        text = f"```json\n{text}\n```"
    return {"output": {"message": {"content": [{"text": text}]}}}


class TestProposeNextStep:
    def test_no_matches_escalates_to_human(self, agent):
        proposed = agent.propose_next_step(matches=[], step_index=0)

        assert proposed.action == "page_on_call_engineer"
        assert proposed.based_on_incident_id is None
        assert proposed.source == SOURCE_NO_PRECEDENT

    def test_bedrock_reasoning_used_when_available(self, agent):
        matches = [CorrelationMatch(incident_id="id-1", summary="past incident", state="resolved", distance=0.1)]
        mock_client = MagicMock()
        mock_client.converse.return_value = _bedrock_response("restart_connection_pool", "Matches closest precedent.")

        with patch("agents.remediation_agent.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            proposed = agent.propose_next_step(matches, step_index=0, alert_text="latency spike")

        assert proposed.action == "restart_connection_pool"
        assert proposed.based_on_incident_id == "id-1"
        assert proposed.source == SOURCE_BEDROCK
        mock_client.converse.assert_called_once()

    def test_bedrock_response_wrapped_in_code_fence_is_parsed(self, agent):
        matches = [CorrelationMatch(incident_id="id-1", summary="past incident", state="resolved", distance=0.1)]
        mock_client = MagicMock()
        mock_client.converse.return_value = _bedrock_response("drain_connection_pool", "Fenced response.", fenced=True)

        with patch("agents.remediation_agent.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            proposed = agent.propose_next_step(matches, step_index=0)

        assert proposed.action == "drain_connection_pool"

    def test_falls_back_to_precedent_replay_when_bedrock_unreachable(self, agent):
        matches = [CorrelationMatch(incident_id="id-1", summary="past incident", state="resolved", distance=0.2345)]
        mock_client = MagicMock()
        mock_client.converse.side_effect = RuntimeError("throttled")

        with patch("agents.remediation_agent.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            proposed = agent.propose_next_step(matches, step_index=2)

        assert proposed.action == "replay_remediation_from_incident_id-1_step_2"
        assert proposed.based_on_incident_id == "id-1"
        assert "0.2345" in proposed.rationale
        assert proposed.source == SOURCE_PRECEDENT_REPLAY

    def test_fenced_bedrock_response_still_reports_bedrock_source(self, agent):
        """The fallback and the fenced-success path both produce a valid action,
        so `source` is the only thing that distinguishes them. Pin it — a
        regression here makes a throttled account look like a healthy one."""
        matches = [CorrelationMatch(incident_id="id-1", summary="past incident", state="resolved", distance=0.1)]
        mock_client = MagicMock()
        mock_client.converse.return_value = _bedrock_response("scale_out_replicas", "Fenced.", fenced=True)

        with patch("agents.remediation_agent.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            proposed = agent.propose_next_step(matches, step_index=0)

        assert proposed.source == SOURCE_BEDROCK

    def test_client_created_lazily(self, agent):
        assert agent._bedrock is None
