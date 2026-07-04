# CLAUDE.md

Project context for Claude Code / agentic coding assistants working in this repo.

## What this project is
Continuum — an agentic incident-response system built for the CockroachDB × AWS Hackathon 2026. The single differentiating claim: the agent's memory (incident state + remediation progress) survives the agent process being killed mid-incident, because it lives in CockroachDB, not in local process memory.

## Non-negotiable constraints
- **All incident/alert/remediation data is synthetic.** Never introduce real company names, real infra, or anything resembling real credentials into seed data, code comments, or docs.
- **Every write to incident or remediation state goes through `agents/memory_agent.py`.** No other module should issue raw writes to `incidents` or `remediation_steps` — this single-write-path property is load-bearing for ADR 001/003, don't casually add a second one.
- **The orchestrator (`agents/orchestrator.py`) must not assume warm state.** Its first action on every invocation is a CockroachDB read to check for existing open incident state before doing anything else. Do not add any in-memory caching of incident state across invocations — that would silently break the resilience guarantee this project is built to prove.
- **Code built during the Submission Period only** (June 30 – Aug 18, 2026, per hackathon rules) — do not port logic from `argus` or `bankers-wrapped` repos wholesale; architectural *patterns* are fine to reuse, code is not.

## Style / conventions (matching sibling repos `argus`, `bankers-wrapped`)
- Python 3.14, psycopg 3 (psycopg2 has no 3.14 wheels); async where I/O-bound (DB calls, Bedrock calls)
- structlog JSON logging (`observability/structured_logger.py`) — no bare `print`
- Pydantic models for all structured data crossing an agent boundary
- Makefile targets are the source of truth for how to run anything — keep README Quick Start in sync with the Makefile, not the other way around
- ADRs go in `docs/adr/`, numbered sequentially, one decision per file

## Where things live
- Schema: `infra/schema.sql` — the dual transactional/vector memory model, read this before touching any DB code
- Architecture spec: `docs/ARCHITECTURE.md`
- Demo script: `docs/DEMO_RUNBOOK.md` — the kill-and-recover sequence is the thing being graded, treat changes to that flow as high-risk

## When adding a CockroachDB or AWS integration
Ask first: does this tool have a real job in the demo, or is it being added to hit the "2+ tools" checklist? If the latter, don't add it — see ADR 004 for the reasoning. Decorative integrations hurt the Technical Implementation score more than they help eligibility.
