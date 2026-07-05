# ADR 004: ccloud CLI's Job Is Backup/Replication Verification, Not Decoration

## Status
Accepted

## Context
The hackathon requires 2+ CockroachDB tools "meaningfully integrated — not just initialized." A common failure mode in hackathon submissions is including a third tool via one throwaway script (e.g., listing clusters once) purely to hit a checkbox. That reads as decorative to judges and can hurt the Technical Implementation score rather than help it.

## Decision
If ccloud CLI is included at all, its only job is: before the chaos-kill demo runs, verify that the CockroachDB cluster's backups and cross-region replication are healthy (`ccloud cluster backup list`, `ccloud cluster describe` style checks, exact commands TBD against current ccloud CLI docs at build time). This ties directly into the project's narrative — a memory system that can't verify its own durability isn't trustworthy — rather than being a standalone integration.

## Consequences
- If build time runs short, this is the first thing cut — 2 tools done well (Vector Index + MCP Server) beats 3 tools done thin, per our own scoring discussion
- If included, it must appear in the demo video doing this specific check, not just in a README bullet point

## Resolution
Cut. Continuum's two CockroachDB tools are **Distributed Vector Indexing** (`correlation_agent.py`) and the **Managed MCP Server** (`agents/query_agent.py`, ADR 003) — both load-bearing in the running application, satisfying the "≥2 tools, meaningfully integrated" requirement without a third, thinner integration. ccloud CLI is not referenced in the submission as a tool used; it remains available as roadmap work (ADR 006) if there's time after the core demo is solid.
