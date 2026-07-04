# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] — working core

### Added
- Real Amazon Bedrock wiring: Titan Text Embeddings V2 (1024-dim, matching `VECTOR(1024)` schema) in the Correlation Agent; Claude-on-Bedrock reasoning with deterministic precedent-replay fallback in the Remediation Agent
- Genuinely interruptible remediation loop: each invocation drives one step through `proposed → executing → executed` with a simulated execution window; a kill mid-step leaves `executing` durably in CockroachDB and the next cold invocation re-runs that exact step
- Cross-platform `chaos_kill.py` (psutil) + `scripts/chaos_demo.ps1` for Windows; fixed `make chaos-demo` to actually kill the process doing the work
- Seeded historical incidents now include their remediation step history, so precedent replay has real precedent
- CI quality gate (`.github/workflows/ci.yml`): Ruff → pytest (5 recovery-semantics unit tests) → coverage → Codecov
- `pyproject.toml` (Python 3.14, Ruff, pytest/coverage config)

### Changed
- Python 3.12 → 3.14; psycopg2 → psycopg 3 (no cp314 wheels for psycopg2); dependencies switched to floor pins that resolve to latest
- Schema: `VECTOR(1536)` → `VECTOR(1024)` (Titan v2's max output dimension — 1536 was unsatisfiable)
- README rebuilt to submission grade: logo, CI/coverage badges, brand-colored Mermaid architecture, recovery-timeline table, tech-stack badge table, CI/CD + screenshots sections

### Earlier (scaffold)
- Initial project scaffold: README, ARCHITECTURE, ADRs 001–006, SUBMISSION checklist, DEMO_RUNBOOK
- CockroachDB schema: `incidents`, `remediation_steps`, `incident_embeddings` with vector index (`infra/schema.sql`)
- Agent module stubs: orchestrator, correlation, memory, remediation
- Synthetic data generation scripts (stubs)
- Chaos-kill script for resilience demo (stub)
- Hugging Face Spaces deployment: README frontmatter, `.github/workflows/sync-to-hf-space.yml`, `docs/DEPLOY.md` — free, cardless public hosting for the Gradio demo UI, replacing the Railway/Vercel/Next.js stack considered and rejected for this project (no frontend framework needed, judged surface is the CockroachDB memory layer)

### Planned
- Agent implementation (correlation via CockroachDB vector search, remediation reasoning via Bedrock)
- Lambda deployment (SAM template)
- Gradio demo UI
- MCP Server read-only query examples
- ccloud CLI backup/replication verification (stretch — ADR 004)
- Demo video recording per `docs/DEMO_RUNBOOK.md`

## [0.1.0] — scaffold
- Repository initialized for CockroachDB × AWS Hackathon 2026 submission
