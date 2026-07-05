# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.3.0] — 2026-07-05 — demo Space redesigned as a live incident-memory console

### Added
- **`ui/app.py` rebuilt into a dark, NOC-style incident console** (from a single Dataframe). The resilience story is now visible on screen, not only in the video:
  - **Recovery timeline** drill-down — pick an incident and replay its `remediation_steps` log; the step stuck in `executing` pulses and is flagged *"the process died here — the next cold invocation resumes at exactly this step"*
  - **Resilience banner** that reads the live count of in-flight (`executing`) steps and states the resume guarantee in plain terms
  - **KPI tiles** (Open · In-flight now · Resolved · Steps committed) using the accessible status palette (icon + label, never colour alone)
  - **Incident cards** with a per-incident mini step-tracker, and `gr.Timer` auto-refresh (5s) so the feed stays live during the demo
  - Still read-only: direct psycopg for the feed, `query_agent` (MCP) for the "Ask via MCP" panel — `memory_agent.py` remains the only write path
- Static preview of the console for design review (rendered from the app's own functions over synthetic incidents)

### Changed
- Space now pins **Gradio 6** (`sdk_version: 6.19.0` in README frontmatter; `requirements.txt` floor `gradio>=6.0`), matching the development environment
- README Screenshots / Demo-UI wording updated to describe the console + recovery timeline rather than a bare incident feed
- `docs/DEPLOY.md` and `docs/DEMO_RUNBOOK.md` updated to reflect the new UI (recovery-timeline drill-down as the demo's visual proof) and the Gradio-6 pin

### Fixed
- **HF Space build was broken in 0.2.0**: `app_file: ui/app.py` is in a subdirectory, so running it as a script put `ui/` (not the repo root) on `sys.path`, and `from agents…`/`from config…` failed with `ModuleNotFoundError`. `ui/app.py` now bootstraps the repo root onto `sys.path` before those imports
- Gradio 5→6 API move: `css`/`theme`/`js` relocated from `Blocks()` to `launch()`. The stylesheet is now injected as a `<style>` component (renders on any version) and `launch()` kwargs are guarded by a signature check, so the app can't crash on a version mismatch

## [0.2.0] — 2026-07-05 — working core, MCP hardening, 100% coverage

### Added
- Real Amazon Bedrock wiring: Titan Text Embeddings V2 (1024-dim, matching `VECTOR(1024)` schema) in the Correlation Agent; Claude-on-Bedrock reasoning with deterministic precedent-replay fallback in the Remediation Agent
- Genuinely interruptible remediation loop: each invocation drives one step through `proposed → executing → executed` with a simulated execution window; a kill mid-step leaves `executing` durably in CockroachDB and the next cold invocation re-runs that exact step
- Cross-platform `chaos_kill.py` (psutil) + `scripts/chaos_demo.ps1` for Windows; fixed `make chaos-demo` to actually kill the process doing the work
- Seeded historical incidents now include their remediation step history, so precedent replay has real precedent
- CI quality gate (`.github/workflows/ci.yml`): Ruff → pytest → coverage → Codecov
- `pyproject.toml` (Python 3.14, Ruff, pytest/coverage config)
- **`agents/query_agent.py`** — a real client of the CockroachDB Cloud Managed MCP Server (official `mcp` SDK, streamable HTTP), called by the running app itself via `GET /api/v1/incidents/open` and the Gradio UI's "Ask via MCP" panel, not only by Claude Code during development (ADR 003 amended). This and Distributed Vector Indexing are Continuum's two CockroachDB tools; ccloud CLI was evaluated and cut (ADR 004 resolution, ADR 006)
- Real integration test (`tests/integration/test_recovery_e2e.py`) exercising the actual kill-and-recover cycle against a live CockroachDB instance — previously a stub that always skipped itself
- CI now provisions an ephemeral single-node CockroachDB container so the integration suite runs on every push, not only when a developer happens to have a cluster handy
- Unit test suite grew from 5 to 42 tests (one file per agent/module: memory, correlation, remediation, query agent, API, observability) — coverage 60% → 100%; CI gate raised 60% → 90%
- `.github/workflows/release.yml` — tags matching `v*.*.*` cut a GitHub Release with notes pulled from this file
- `docs/adr/007-eu-central-1-region.md` — documents the deployment region and cross-region inference profile choice
- Project-level `.claude/settings.json` — safe read-only + build/test command allowlist, ruff-autofix-on-edit hook

### Changed
- Python 3.12 → 3.14; psycopg2 → psycopg 3 (no cp314 wheels for psycopg2); dependencies switched to floor pins that resolve to latest
- Schema: `VECTOR(1536)` → `VECTOR(1024)` (Titan v2's max output dimension — 1536 was unsatisfiable)
- README rebuilt to submission grade: logo, CI/coverage badges, brand-colored Mermaid architecture, recovery-timeline table, tech-stack badge table, CI/CD + screenshots sections
- AWS region `us-east-1` → `eu-central-1`; Bedrock reasoning model to `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` (EU cross-region inference profile) — kept in sync across `.env.example`, `config.py`, `infra/template.yaml` (ADR 007)
- `infra/template.yaml` Lambda runtime `python3.12` → `python3.14`, matching the rest of the codebase
- CLAUDE.md expanded (Key Commands, Architecture, Testing Strategy, Deployment, Judging Criteria) to match sibling-repo conventions

### Fixed
- `config.Settings` crashed at import — and thus the whole app failed to start — for anyone with ordinary `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` in their environment (pydantic-settings defaults to `extra="forbid"`, and those two vars were never declared fields). Now `extra="ignore"`
- `infra/template.yaml` targeted a Lambda runtime (3.12) that couldn't run this codebase's 3.14-only dependencies

### Removed
- `docs/continuum-DEPLOY.md` — an exact duplicate of `docs/DEPLOY.md`

### Earlier (scaffold)
- Initial project scaffold: README, ARCHITECTURE, ADRs 001–006, SUBMISSION checklist, DEMO_RUNBOOK
- CockroachDB schema: `incidents`, `remediation_steps`, `incident_embeddings` with vector index (`infra/schema.sql`)
- Agent module stubs: orchestrator, correlation, memory, remediation
- Synthetic data generation scripts (stubs)
- Chaos-kill script for resilience demo (stub)
- Hugging Face Spaces deployment: README frontmatter, `.github/workflows/sync-to-hf-space.yml`, `docs/DEPLOY.md` — free, cardless public hosting for the Gradio demo UI, replacing the Railway/Vercel/Next.js stack considered and rejected for this project (no frontend framework needed, judged surface is the CockroachDB memory layer)

### Planned (before submission)
- Demo video recording per `docs/DEMO_RUNBOOK.md`
- Deploy orchestrator to AWS Lambda (SAM) and confirm the Hugging Face Space is live
- Complete the `docs/SUBMISSION.md` checklist end to end

## [0.1.0] — scaffold
- Repository initialized for CockroachDB × AWS Hackathon 2026 submission
