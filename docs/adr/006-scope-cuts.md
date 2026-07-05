# ADR 006: Documented Scope Cuts

## Status
Accepted

## Context
Solo build, ~7-week submission window (June 30 – Aug 18, 2026). Several adjacent ideas were explicitly considered and rejected to protect the core memory-recovery demo from scope creep. Documenting them here so "why isn't X included" has a clear answer.

## Cuts

- **No GPU fleet / NVIDIA NIM routing agent** ("Fleet Mind" concept). Real GPU infra cost and setup time would compete directly with time spent on CockroachDB memory logic — the part that's actually graded. Rejected in favor of Continuum's synthetic, infra-light alert stream.
- **No real alerting integration** (PagerDuty/Opsgenie). Adds OAuth/webhook plumbing with no scoring benefit over a deterministic synthetic stream.
- **No multi-region deployment in the MVP.** Schema supports it (`region` columns, prefix-partitioned vector index) but only single-region is demoed, to keep AWS/CockroachDB cluster setup within free-tier and within build time.
- **No custom RBAC layer.** Relies on MCP Server's default safe/read-only posture rather than building bespoke access control — noted as roadmap.
- **No ccloud CLI integration** (see ADR 004's resolution). Vector Indexing + MCP Server already satisfy the "≥2 CockroachDB tools, meaningfully integrated" requirement; a third, thinner integration would cost build time without adding score.

## Consequences
Smaller demo surface area, but every included piece is meant to be built and demonstrated properly rather than partially. This directly follows from the earlier project-selection analysis: a tight MVP with one well-executed resilience story scores higher across equally-weighted criteria than a broader build that runs out of time before any one piece is production-quality.
