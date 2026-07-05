"""Unit tests for the FastAPI gateway — mocks handle_alert and QueryAgent so
no real CockroachDB/Bedrock/MCP calls happen."""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from agents.query_agent import QueryResult
from api.main import app

client = TestClient(app)


class TestHealth:
    def test_health_returns_ok(self):
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestPostAlert:
    def test_post_alert_delegates_to_orchestrator(self):
        payload = {
            "correlation_id": "corr-1",
            "service": "checkout-api",
            "severity": "high",
            "text": "latency spike",
        }
        with patch("api.main.handle_alert", return_value={"incident_id": "abc", "state": "remediating"}) as mock_handle:
            response = client.post("/api/v1/alert", json=payload)

        assert response.status_code == 200
        assert response.json()["state"] == "remediating"
        mock_handle.assert_called_once()
        called_alert = mock_handle.call_args[0][0]
        assert called_alert["correlation_id"] == "corr-1"
        assert called_alert["region"] == "default"  # default applied when omitted


class TestOpenIncidents:
    def test_returns_rows_from_query_agent(self):
        result = QueryResult(rows=[{"incident_id": "abc", "state": "remediating"}], row_count=1)
        with patch("api.main.query_agent") as mock_agent:
            mock_agent.list_open_incidents = AsyncMock(return_value=result)
            response = client.get("/api/v1/incidents/open")

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert body["incidents"][0]["incident_id"] == "abc"

    def test_returns_503_when_mcp_unavailable(self):
        with patch("api.main.query_agent") as mock_agent:
            mock_agent.list_open_incidents = AsyncMock(side_effect=RuntimeError("mcp endpoint unreachable"))
            response = client.get("/api/v1/incidents/open")

        assert response.status_code == 503
