"""
Query Agent — Continuum's own client for the CockroachDB Cloud Managed MCP
Server (read-only). This is what makes MCP a real second CockroachDB tool
per ADR 003: the running application calls it over the MCP protocol, rather
than it only being a convenience for Claude Code / Cursor during development.

Never a write path — memory_agent.py remains the only module permitted to
write incident/remediation state (CLAUDE.md, ADR 003).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from config import settings
from observability.structured_logger import get_logger

log = get_logger(__name__)

# Read-only SQL tool exposed by the CockroachDB Cloud Managed MCP Server.
# Confirm the exact name against the live console-generated config snippet
# before the demo — the server is safe-by-default read-only regardless of
# which tool name is current, so a rename here is a config fix, not a
# security concern.
_SELECT_QUERY_TOOL = "select_query"

# The live query-interface beat: "what's open right now" (README, ADR 003).
_OPEN_INCIDENTS_SQL = (
    "SELECT incident_id, service, state, opened_at FROM incidents "
    "WHERE state NOT IN ('resolved', 'escalated') ORDER BY opened_at DESC LIMIT 50"
)


@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    row_count: int


class QueryAgent:
    """Read-only live query interface against CockroachDB via its Managed
    MCP Server, over streamable HTTP."""

    def __init__(self, endpoint: str | None = None, api_key: str | None = None,
                 cluster_id: str | None = None, database: str | None = None) -> None:
        self._endpoint = endpoint or settings.cockroach_mcp_endpoint
        # None = "use settings"; an explicit "" stays blank (tests rely on
        # this to stay hermetic regardless of what the local .env sets).
        self._api_key = settings.cockroach_mcp_api_key if api_key is None else api_key
        self._cluster_id = settings.cockroach_mcp_cluster_id if cluster_id is None else cluster_id
        self._database = database or settings.cockroach_mcp_database

    def _headers(self) -> dict[str, str]:
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        # Scopes the MCP session to one cluster — the server rejects queries
        # with "cluster_id not provided" without it.
        if self._cluster_id:
            headers["mcp-cluster-id"] = self._cluster_id
        return headers

    async def run_readonly_query(self, sql: str) -> QueryResult:
        async with streamablehttp_client(self._endpoint, headers=self._headers()) as (
            read,
            write,
            _get_session_id,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    _SELECT_QUERY_TOOL, {"query": sql, "database": self._database}
                )
                rows = _extract_rows(result)
                log.info("mcp_query_executed", tool=_SELECT_QUERY_TOOL, row_count=len(rows))
                return QueryResult(rows=rows, row_count=len(rows))

    async def list_open_incidents(self) -> QueryResult:
        return await self.run_readonly_query(_OPEN_INCIDENTS_SQL)


def _extract_rows(result: Any) -> list[dict[str, Any]]:
    """MCP tool results may carry structured JSON directly, or as a text
    block containing a JSON payload — handle both."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, list):
        return structured
    if isinstance(structured, dict):
        rows = structured.get("rows", structured)
        if isinstance(rows, list):
            return rows

    for block in getattr(result, "content", []):
        text = getattr(block, "text", None)
        if text:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return parsed.get("rows", [])
    return []
