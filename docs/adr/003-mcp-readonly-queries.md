# ADR 003: MCP Server Used Read-Only

## Status
Accepted

## Context
The CockroachDB Cloud Managed MCP Server supports safe-by-default read-only mode with full audit logging. Continuum could request write access to let the MCP client directly mutate incident state, but the agents already own all writes through `memory_agent.py`.

## Decision
Connect the MCP Server in read-only mode only. It is used as a live query/inspection interface (for the demo, and for development in Claude Code / Cursor) — never as a write path.

## Consequences
- Keeps a single, auditable write path (`memory_agent.py` → CockroachDB) rather than two ways to mutate state, which would reintroduce the consistency risk ADR 001 was written to avoid
- Matches the MCP Server's own safe-by-default posture rather than working around it
- The demo's "ask a live question about the fleet" beat (e.g. *"what's open right now"*) is fully supported without any write-path risk
