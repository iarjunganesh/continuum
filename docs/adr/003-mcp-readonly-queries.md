# ADR 003: MCP Server Used Read-Only

## Status
Accepted (amended — see Update below)

## Context
The CockroachDB Cloud Managed MCP Server supports safe-by-default read-only mode with full audit logging. Continuum could request write access to let the MCP client directly mutate incident state, but the agents already own all writes through `memory_agent.py`.

## Decision
Connect the MCP Server in read-only mode only. It is used as a live query/inspection interface — never as a write path.

## Consequences
- Keeps a single, auditable write path (`memory_agent.py` → CockroachDB) rather than two ways to mutate state, which would reintroduce the consistency risk ADR 001 was written to avoid
- Matches the MCP Server's own safe-by-default posture rather than working around it
- The demo's "ask a live question about the fleet" beat (e.g. *"what's open right now"*) is fully supported without any write-path risk

## Update: the running application is the MCP client, not just Claude Code
The first version of this ADR only had MCP wired into Claude Code / Cursor during development — a real convenience, but not something the *agent* did, which is a thin reading of "meaningfully integrated" per the hackathon rules. `agents/query_agent.py` now connects to `COCKROACH_MCP_ENDPOINT` directly (official `mcp` Python SDK, streamable HTTP transport) and calls the server's read-only SQL tool at runtime — exposed at `GET /api/v1/incidents/open` and the "Ask via MCP" button in the Gradio UI. Claude Code/Cursor access to the same endpoint during development still stands, but it's no longer the only thing backing this tool's inclusion.
