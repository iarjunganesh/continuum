# CLAUDE.md

Project context for Claude Code / agentic coding assistants working in this repo.

## What this project is
Continuum — an agentic incident-response system built for the CockroachDB × AWS Hackathon 2026. The single differentiating claim: the agent's memory (incident state + remediation progress) survives the agent process being killed mid-incident, because it lives in CockroachDB, not in local process memory.

**Current phase**: core build complete — recovery loop, dual memory model, explicit per-step `SERIALIZABLE` transactions + concurrency-safe exactly-once (ADR 009), best-effort Bedrock correlation, both CockroachDB tools, 100% unit coverage, a real (not stubbed) integration test against a live cluster. The Hugging Face Space is deployed and live (`docs/DEPLOY.md`); synthetic seeding is blocked on an AWS-side Bedrock quota/model-access issue, not code (a precomputed-embedding fixture path is planned to decouple the demo from live Bedrock). Remaining before submission: deploy the orchestrator to Lambda, add a benchmark table, record the demo video (`docs/DEMO_RUNBOOK.md`), fill in the `docs/SUBMISSION.md` checklist end to end.

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
4. `memory_agent.py` — the *only* module permitted to write `incidents`/`remediation_steps`; the orchestrator's per-step writes go through `checkpoint_step_start`/`checkpoint_step_done`, two explicit `SERIALIZABLE` transactions with the execution window between them (ADR 009)
5. `query_agent.py` — CockroachDB Managed MCP Server client (read-only), called by the app itself via `GET /api/v1/incidents/open` and the Gradio UI, not only by Claude Code during development (ADR 003)

CockroachDB tools used: **Distributed Vector Indexing** + **Managed MCP Server** — both load-bearing in the running app. ccloud CLI was evaluated and cut (ADR 004) rather than added as a thinner third integration. AWS: **Lambda** (orchestrator execution, no provisioned concurrency) + **Bedrock** (Titan embeddings, Claude reasoning).

## Non-negotiable constraints
- **All incident/alert/remediation data is synthetic.** Never introduce real company names, real infra, or anything resembling real credentials into seed data, code comments, or docs.
- **Every write to incident or remediation state goes through `agents/memory_agent.py`.** No other module should issue raw writes to `incidents` or `remediation_steps` — this single-write-path property is load-bearing for ADR 001/003, don't casually add a second one.
- **The orchestrator (`agents/orchestrator.py`) must not assume warm state.** Its first action on every invocation is a CockroachDB read to check for existing open incident state before doing anything else. Do not add any in-memory caching of incident state across invocations — that would silently break the resilience guarantee this project is built to prove.
- **The two-phase step checkpoint is load-bearing (ADR 009).** `checkpoint_step_start` commits the step as `executing` *before* the `time.sleep` execution window; `checkpoint_step_done` commits `executed` *after*. Keep them as two separate transactions with the sleep between them — a kill must land with `executing` durable. Keep the forward-step claim as `INSERT ... ON CONFLICT DO NOTHING`: switching it to `DO UPDATE` silently breaks exactly-once under concurrent invocations. Correlation/Bedrock in STEP 2 is deliberately wrapped in try/except (best-effort) so a Bedrock outage degrades to "no precedent" instead of aborting the incident before it's durable — don't make it fatal.
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
- `tests/integration/test_recovery_e2e.py` — drives the resume + exactly-once contract against a live CockroachDB instance (the kill is injected as the durable `executing` state a real `chaos_kill.py` strike leaves; correlation/remediation mocked, memory agent and schema real). `test_forward_step_claim_is_exactly_once` proves the `ON CONFLICT` claim guard on a real cluster. Skips if `COCKROACH_DATABASE_URL` isn't set; the literal OS process-kill is exercised by `scripts/chaos_kill.py` / `chaos_demo.ps1` in the demo.
- CI runs an ephemeral single-node CockroachDB container so the integration suite actually executes on every push, not just locally when a dev happens to have a cluster handy

## Deployment
- Region: **eu-central-1** — co-locates the Lambda with the CockroachDB Cloud cluster (ADR 007). Keep `AWS_REGION` / `config.py` defaults / `infra/template.yaml` in sync; a drift between them fails silently as a Bedrock access error, not a config error.
- Bedrock calls target a **separate** `BEDROCK_REGION` (default `eu-west-1`), not `AWS_REGION` — this account has a hard, non-adjustable `0` on-demand/cross-region Bedrock quota in eu-central-1 (and us-east-1) for every model (ADR 008). This is intentional, not the drift the line above warns about; don't "fix" it back to `AWS_REGION`.
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
