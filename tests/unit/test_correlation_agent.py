"""Unit tests for CorrelationAgent — mocks boto3 (Bedrock) and psycopg
(CockroachDB vector search). No real AWS or DB calls."""
import json
from unittest.mock import MagicMock, patch

import pytest

from agents.correlation_agent import CorrelationAgent, CorrelationMatch
from config import settings


@pytest.fixture
def agent() -> CorrelationAgent:
    return CorrelationAgent(dsn="postgresql://mock:mock@localhost:26257/defaultdb")


class TestEmbed:
    def test_embed_returns_vector_from_bedrock_response(self, agent):
        embedding = [0.1] * 1024
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({"embedding": embedding}).encode()
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = {"body": mock_body}

        with patch("agents.correlation_agent.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            result = agent.embed("elevated p99 latency")

        assert result == embedding
        mock_client.invoke_model.assert_called_once()
        _, kwargs = mock_client.invoke_model.call_args
        body = json.loads(kwargs["body"])
        assert body["inputText"] == "elevated p99 latency"
        assert body["normalize"] is True

    def test_client_is_created_lazily_and_reused(self, agent):
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({"embedding": [0.0]}).encode()
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = {"body": mock_body}

        with patch("agents.correlation_agent.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            agent.embed("alert one")
            agent.embed("alert two")

        mock_boto3.client.assert_called_once()
        args, kwargs = mock_boto3.client.call_args
        assert args == ("bedrock-runtime",)
        assert kwargs["region_name"] == settings.bedrock_region
        # Explicit timeouts/capped retries so a throttled call can't eat the
        # Lambda invocation budget (ADR 008 addendum).
        assert kwargs["config"].read_timeout == 15
        assert kwargs["config"].retries == {"max_attempts": 2, "mode": "standard"}


class TestFindSimilar:
    def test_returns_correlation_matches_ordered_by_distance(self, agent):
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"incident_id": "id-1", "summary": "past incident A", "state": "resolved", "distance": 0.12},
            {"incident_id": "id-2", "summary": "past incident B", "state": "resolved", "distance": 0.45},
        ]

        with patch("agents.correlation_agent.psycopg") as mock_psycopg:
            mock_psycopg.connect.return_value.__enter__.return_value = conn
            conn.cursor.return_value.__enter__.return_value = cur
            matches = agent.find_similar("checkout-api", [0.1] * 1024, k=5)

        assert len(matches) == 2
        assert all(isinstance(m, CorrelationMatch) for m in matches)
        assert matches[0].incident_id == "id-1"
        assert matches[0].distance == 0.12

    def test_filters_by_service_and_limits_k(self, agent):
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = []

        with patch("agents.correlation_agent.psycopg") as mock_psycopg:
            mock_psycopg.connect.return_value.__enter__.return_value = conn
            conn.cursor.return_value.__enter__.return_value = cur
            agent.find_similar("auth-service", [0.0] * 1024, k=3)

        params = cur.execute.call_args[0][1]
        assert params[1] == "auth-service"
        assert params[-1] == 3

    def test_returns_empty_list_when_no_matches(self, agent):
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = []

        with patch("agents.correlation_agent.psycopg") as mock_psycopg:
            mock_psycopg.connect.return_value.__enter__.return_value = conn
            conn.cursor.return_value.__enter__.return_value = cur
            matches = agent.find_similar("checkout-api", [0.0] * 1024)

        assert matches == []
