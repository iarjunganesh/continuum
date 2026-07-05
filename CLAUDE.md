# CLAUDE.md

Project context for Claude Code / agentic coding assistants working in this repo.

## What this project is
Continuum — an agentic incident-response system built for the CockroachDB × AWS Hackathon 2026. The single differentiating claim: the agent's memory (incident state + remediation progress) survives the agent process being killed mid-incident, because it lives in CockroachDB, not in local process memory.

**Current phase**: core build complete — recovery loop, dual memory model, both CockroachDB tools, Lambda + Bedrock, 100% unit coverage, a real (not stubbed) integration test against a live cluster. Remaining before submission: cut a GitHub release, record the demo video (`docs/DEMO_RUNBOOK.md`), deploy to Hugging Face Spaces + Lambda, fill in the `docs/SUBMISSION.md` checklist end to end.

## Key Commands
```bash
make install      # pip install -r requirements.txt
make migrate      # apply infra/schema.sql to $COCKROACH_DATABASE_URL
make seed-data     # generate + load synthetic incidents (with embeddings)
make run-api      # uvicorn api.main:app --port 8000
make run-ui       # python ui/app.py (Gradio)
make chaos-demo   # the kill-and-recover sequence — see docs/DEMO_RUNBOOK.md
make test         # pytest tests/unit tests/integration -v
make coverage     # pytest --cov=agents --cov=api --cov=observability --cov-report=term-missing
make lint         # ruff check .
```
`tests/integration` requires a live CockroachDB at `$COCKROACH_DATABASE_URL` and skips gracefully without one; CI provides one via an ephemeral single-node container (`.github/workflows/ci.yml`), so `make test` locally without a cluster only runs the unit suite in practice.

## Architecture
Five agents, one write path (see `docs/ARCHITECTURE.md` for the full spec):

1. `orchestrator.py` — Lambda entrypoint; recovery-read-first control flow (ADR 002)
2. `correlation_agent.py` — Bedrock Titan embeddings + CockroachDB vector search
3. `remediation_agent.py` — Claude-on-Bedrock reasoning + deterministic precedent-replay fallback
4. `memory_agent.py` — the *only* module permitted to write `incidents`/`remediation_steps`
5. `query_agent.py` — CockroachDB Managed MCP Server client (read-only), called by the app itself via `GET /api/v1/incidents/open` and the Gradio UI, not only by Claude Code during development (ADR 003)

CockroachDB tools used: **Distributed Vector Indexing** + **Managed MCP Server** — both load-bearing in the running app. ccloud CLI was evaluated and cut (ADR 004) rather than added as a thinner third integration. AWS: **Lambda** (orchestrator execution, no provisioned concurrency) + **Bedrock** (Titan embeddings, Claude reasoning).

## Non-negotiable constraints
- **All incident/alert/remediation data is synthetic.** Never introduce real company names, real infra, or anything resembling real credentials into seed data, code comments, or docs.
- **Every write to incident or remediation state goes through `agents/memory_agent.py`.** No other module should issue raw writes to `incidents` or `remediation_steps` — this single-write-path property is load-bearing for ADR 001/003, don't casually add a second one.
- **The orchestrator (`agents/orchestrator.py`) must not assume warm state.** Its first action on every invocation is a CockroachDB read to check for existing open incident state before doing anything else. Do not add any in-memory caching of incident state across invocations — that would silently break the resilience guarantee this project is built to prove.
- **Code built during the Submission Period only** (June 30 – Aug 18, 2026, per hackathon rules) — do not port logic from `argus` or `bankers-wrapped` repos wholesale; architectural *patterns* are fine to reuse, code is not.
- **`config.Settings` must tolerate unknown env vars** (`extra="ignore"`) — it is not the only consumer of the process environment (boto3 reads `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` itself). Reintroducing `extra="forbid"` breaks app startup for anyone with ordinary AWS credentials exported.

## Style / conventions (matching sibling repos `argus`, `bankers-wrapped`)
- Python 3.14, psycopg 3 (psycopg2 has no 3.14 wheels); async where I/O-bound (DB calls, Bedrock calls, MCP calls)
- structlog JSON logging (`observability/structured_logger.py`) — no bare `print`
- Pydantic models for all structured data crossing an agent boundary
- Makefile targets are the source of truth for how to run anything — keep README Quick Start in sync with the Makefile, not the other way around
- ADRs go in `docs/adr/`, numbered sequentially, one decision per file
- Tests: mock at the module boundary (`patch("agents.x.boto3")`, `patch("agents.x.psycopg")`), never mock the class under test itself — see `tests/unit/` for the established pattern per agent

## Testing Strategy
- `tests/unit/` — one file per agent/module; all external I/O (psycopg, boto3, mcp SDK) mocked at the import boundary; coverage gate enforced at 90% (`--cov-fail-under=90` in CI)
- `tests/integration/test_recovery_e2e.py` — the real kill-and-recover cycle against a live CockroachDB instance (correlation/remediation agents mocked, memory agent and schema are real); skips if `COCKROACH_DATABASE_URL` isn't set
- CI runs an ephemeral single-node CockroachDB container so the integration suite actually executes on every push, not just locally when a dev happens to have a cluster handy

## Deployment
- Region: **eu-central-1** — co-locates the Lambda with the CockroachDB Cloud cluster (ADR 007). Keep `AWS_REGION` / `config.py` defaults / `infra/template.yaml` in sync; a drift between them fails silently as a Bedrock access error, not a config error.
- Lambda runtime: `python3.14` (`infra/template.yaml`) — matches the rest of the codebase; do not downgrade to chase an older SAM example.
- Demo UI: Gradio on Hugging Face Spaces (`docs/DEPLOY.md`), auto-synced on push to `main` (`.github/workflows/sync-to-hf-space.yml`)

## Where things live
- Schema: `infra/schema.sql` — the dual transactional/vector memory model, read this before touching any DB code
- Architecture spec: `docs/ARCHITECTURE.md`
- Demo script: `docs/DEMO_RUNBOOK.md` — the kill-and-recover sequence is the thing being graded, treat changes to that flow as high-risk

## When adding a CockroachDB or AWS integration
Ask first: does this tool have a real job in the demo, or is it being added to hit the "2+ tools" checklist? If the latter, don't add it — see ADR 004 for the reasoning. Decorative integrations hurt the Technical Implementation score more than they help eligibility.

## Hackathon Deadline & Judging Criteria
Submission due **August 18, 2026, 5 PM ET**. Judging (equally weighted): Agentic Memory Design, Technical Implementation, Real-World Impact, Production Readiness, Creativity & Originality. Full mapping: `docs/DEVPOST.md`.
