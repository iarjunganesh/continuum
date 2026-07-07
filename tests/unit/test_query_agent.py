"""Unit tests for QueryAgent — mocks the mcp SDK's transport/session so no
real network call reaches the CockroachDB Cloud Managed MCP Server."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from agents.query_agent import QueryAgent, _extract_rows


class _AsyncContextManager:
    """Minimal stand-in for the async context managers streamablehttp_client
    and ClientSession return — MagicMock doesn't support `async with` out of
    the box."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc_info):
        return False


def _tool_result(rows=None, structured=None):
    result = MagicMock()
    if structured is not None:
        result.structuredContent = structured
        result.content = []
    else:
        block = MagicMock()
        block.text = json.dumps(rows)
        result.structuredContent = None
        result.content = [block]
    return result


def _wire_mcp(mock_session):
    stream_cm = _AsyncContextManager(("read-stream", "write-stream", lambda: None))
    session_cm = _AsyncContextManager(mock_session)
    return (
        patch("agents.query_agent.streamablehttp_client", return_value=stream_cm),
        patch("agents.query_agent.ClientSession", return_value=session_cm),
    )


def _mock_session(result) -> MagicMock:
    session = MagicMock()
    session.initialize = AsyncMock()
    session.call_tool = AsyncMock(return_value=result)
    return session


class TestRunReadonlyQuery:
    def test_returns_rows_from_text_content(self):
        session = _mock_session(_tool_result(rows=[{"incident_id": "abc"}]))
        p1, p2 = _wire_mcp(session)

        with p1, p2:
            agent = QueryAgent(endpoint="https://example.test/mcp", api_key="test-key")
            result = asyncio.run(agent.run_readonly_query("SELECT 1"))

        assert result.row_count == 1
        assert result.rows == [{"incident_id": "abc"}]
        session.initialize.assert_awaited_once()

    def test_sends_bearer_auth_and_cluster_headers_when_set(self):
        session = _mock_session(_tool_result(rows=[]))
        p1, p2 = _wire_mcp(session)

        with p1 as mock_stream, p2:
            agent = QueryAgent(endpoint="https://example.test/mcp", api_key="secret-key",
                               cluster_id="cluster-uuid-1")
            asyncio.run(agent.run_readonly_query("SELECT 1"))

        _, kwargs = mock_stream.call_args
        assert kwargs["headers"] == {
            "Authorization": "Bearer secret-key",
            "mcp-cluster-id": "cluster-uuid-1",
        }

    def test_no_headers_when_api_key_and_cluster_blank(self):
        session = _mock_session(_tool_result(rows=[]))
        p1, p2 = _wire_mcp(session)

        with p1 as mock_stream, p2:
            agent = QueryAgent(endpoint="https://example.test/mcp", api_key="",
                               cluster_id="")
            asyncio.run(agent.run_readonly_query("SELECT 1"))

        _, kwargs = mock_stream.call_args
        assert kwargs["headers"] == {}

    def test_calls_select_query_tool_with_sql_and_database(self):
        session = _mock_session(_tool_result(rows=[]))
        p1, p2 = _wire_mcp(session)

        with p1, p2:
            agent = QueryAgent(endpoint="https://example.test/mcp", api_key="k",
                               database="demo-db")
            asyncio.run(agent.run_readonly_query("SELECT 1 FROM incidents"))

        args, _ = session.call_tool.call_args
        assert args[0] == "select_query"
        assert args[1] == {"query": "SELECT 1 FROM incidents", "database": "demo-db"}


class TestListOpenIncidents:
    def test_queries_incidents_excluding_terminal_states(self):
        session = _mock_session(_tool_result(rows=[]))
        p1, p2 = _wire_mcp(session)

        with p1, p2:
            agent = QueryAgent(endpoint="https://example.test/mcp", api_key="k")
            asyncio.run(agent.list_open_incidents())

        args, _ = session.call_tool.call_args
        sql = args[1]["query"]
        assert "NOT IN ('resolved', 'escalated')" in sql


class TestExtractRows:
    def test_prefers_structured_content_rows_key(self):
        result = _tool_result(structured={"rows": [{"a": 1}]})
        assert _extract_rows(result) == [{"a": 1}]

    def test_structured_content_as_bare_list(self):
        result = _tool_result(structured=[{"a": 1}])
        assert _extract_rows(result) == [{"a": 1}]

    def test_falls_back_to_text_block_json_list(self):
        result = _tool_result(rows=[{"a": 1}, {"a": 2}])
        assert _extract_rows(result) == [{"a": 1}, {"a": 2}]

    def test_falls_back_to_text_block_json_object_with_rows(self):
        result = MagicMock()
        result.structuredContent = None
        block = MagicMock()
        block.text = json.dumps({"rows": [{"a": 1}]})
        result.content = [block]
        assert _extract_rows(result) == [{"a": 1}]

    def test_returns_empty_list_when_nothing_parseable(self):
        result = MagicMock()
        result.structuredContent = None
        result.content = []
        assert _extract_rows(result) == []
