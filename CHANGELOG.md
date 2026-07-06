# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.4.0] — 2026-07-06 — claims-vs-code integrity: real transactions, exactly-once, Bedrock-hardened recovery

### Added

- **Explicit per-step transaction boundaries (ADR 009).** The orchestrator's STEP 3 now goes through `MemoryAgent.checkpoint_step_start` / `checkpoint_step_done`, each an explicit `with conn.transaction()` block (CockroachDB `SERIALIZABLE`), with the `time.sleep` execution window between them so a kill still commits `executing` and nothing else. Makes the "transactional memory" claim literally true, not just per-statement autocommit
- **Concurrency-safe exactly-once forward claim (ADR 009).** A new step is claimed with `INSERT ... ON CONFLICT (incident_id, step_index) DO NOTHING`; a racing invocation that loses the claim skips execution instead of double-running the step. `checkpoint_step_done` guards its transition with `AND status = 'executing'`. Proven on a real cluster by `tests/integration/test_recovery_e2e.py::test_forward_step_claim_is_exactly_once`
- **Best-effort correlation.** Orchestrator STEP 2 (`embed` + `find_similar`) is wrapped in try/except — a throttled/misconfigured Bedrock endpoint now degrades to "no precedent" (remediation falls back to `page_on_call_engineer`) instead of throwing before the incident is durable. Removes the single point of failure that a red Bedrock endpoint (ADR 008's 0-quota risk) posed to the whole recovery demo

### Changed

- Aligned docs/claims to the code after auditing the whole repo: corrected "6 ADRs" → 9, unit-test count → 46 (100% measured coverage against the 90% gate), and the ARCHITECTURE.md §3 recovery sequence (it inaccurately showed a killed step being *skipped*; the code re-runs the interrupted step). `docs/DEMO_RUNBOOK.md` 0:20 now uses `--via-api` (a bare `--tick` runs in-process, leaving nothing for `chaos_kill.py` to strike) and notes `make chaos-demo` is POSIX-only

### Removed

- `MemoryAgent.log_step` / `set_step_status` — dead code once STEP 3 moved to the transactional checkpoints; their docstrings described a mechanism the orchestrator no longer used

## [0.3.2] — 2026-07-05 — Bedrock region split; Anthropic use-case form + EULA agreement resolved

### Fixed
- **eu-central-1 has a `0`, non-adjustable Bedrock quota on this account for every model** (Titan Embed V2 and every Claude Sonnet variant, both on-demand and cross-region) — confirmed via `aws service-quotas list-service-quotas`, not assumed. `seed_memory.py`'s single-transaction seeding was failing silently on the first embedding call and rolling back every record. Added `bedrock_region` (`BEDROCK_REGION`, default `eu-west-1`) used only by the `bedrock-runtime` clients in `correlation_agent.py`/`remediation_agent.py`; `aws_region`/Lambda/CockroachDB stay in eu-central-1 (ADR 007 untouched, split documented in ADR 008)
- **Anthropic models required a one-time, account-wide "use case details" form** (`agreementAvailability: NOT_AVAILABLE` on every Claude version checked, not just 4.5) before any Anthropic model could be invoked — submitted via `aws bedrock put-use-case-for-model-access`, followed by `create-foundation-model-agreement` to accept Claude Sonnet 4.5's EULA specifically. Confirmed via `get-foundation-model-availability`: `agreementAvailability` now `AVAILABLE`
- `seed_memory.py` now retries `ThrottlingException` with exponential backoff (5s → 160s over 6 attempts) and commits per record instead of one final commit for the whole file, so a mid-run throttle no longer discards already-seeded rows

### Known issue (not code — AWS account state)
- Even with the above fixed, this brand-new AWS account still hits sustained `ThrottlingException`/`"Too many tokens per day"` on both Titan Embed V2 and Claude Sonnet 4.5 that a 6-retry/~5-minute backoff didn't clear — an automated new-account trust ramp that published Service Quotas values don't reflect. No CLI lever for this; expect it to loosen with time/usage. `remediation_agent.py`'s deterministic precedent-replay fallback keeps the app functional in the meantime

## [0.3.1] — 2026-07-05 — Space actually boots; Windows setup script; scripts/*.py import fix

### Fixed
- **The 0.3.0 Space still didn't boot**: Gradio's launch-time analytics telemetry compares the app's theme against its built-in themes; built-in themes use `Font` objects for `font`/`font_mono` while ours used plain strings, and Gradio's own `Font.__eq__` doesn't guard against comparing to a non-`Font` — crashing with `AttributeError: 'str' object has no attribute 'name'` whenever analytics is enabled (the Spaces default). Fixed via `analytics_enabled=False` on the `Blocks` constructor, which also means this read-only demo doesn't phone telemetry home
- **`scripts/seed_memory.py`, `demo_run.py`, and `chaos_kill.py` had the same subdir-import bug as `ui/app.py`** (fixed for that file in 0.3.0, missed here): running `python scripts/x.py` puts `scripts/` — not the repo root — on `sys.path`, so `from agents…`/`from config…`/`from observability…` raised `ModuleNotFoundError`. This meant `make seed-data`, `make demo`, and `make chaos-demo` — the actual kill-and-recover sequence `docs/DEMO_RUNBOOK.md` calls the thing being graded — never worked via their documented entrypoints, only discovered while running the Windows seed script end to end for the first time. All three now bootstrap the repo root the same way `ui/app.py` does
- `seed_memory.py` paces its Bedrock embedding calls (1s between records) — a tight back-to-back loop of 40 calls was hitting `ThrottlingException` immediately

### Added
- `scripts/migrate_and_seed.ps1` — Windows equivalent of `make migrate` + `make seed-data` (no `make` on Windows), matching the existing `chaos_demo.ps1` pattern. Checks `COCKROACH_DATABASE_URL` and (unless `-SkipSeed`) AWS credentials up front with a clear message instead of a bare traceback, and checks `$LASTEXITCODE` after every external `python` call — `$ErrorActionPreference = "Stop"` only covers PowerShell cmdlets/terminating errors, not external command exit codes, so a failed step would otherwise print a traceback and the script would carry on and report success anyway (caught by testing the schema step against an unreachable DB)

### Changed
- Space pins **Python 3.14** (`python_version: "3.14"` in README frontmatter), matching CI (`python-version: "3.14"`) and local dev — previously unset, so the Space picked whatever Hugging Face's own default was (observed: 3.13) rather than the project's actual target
- CockroachDB Cloud TLS guidance corrected to `sslmode=require`: `sslrootcert=system` doesn't work for CockroachDB Cloud, since its clusters use a cluster-specific CA rather than one chained to a public root — `verify-full` fails there with `certificate verify failed` even once the root-cert-file-missing error is resolved. `require` encrypts without needing any CA file, an acceptable trade-off since Continuum only ever stores synthetic data (ADR 005) and this connection only ever reaches CockroachDB Cloud's own endpoint

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
