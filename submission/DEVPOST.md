# Devpost Submission — Continuum

## The Hackathon

**[CockroachDB × AWS Hackathon — Build with Agentic Memory](https://cockroachdb-ai.devpost.com/)**

> *Agents that think. Agents that act. Agents that remember; reliably, globally, at any scale.*

Hosted by **Cockroach Labs**, organized by Devpost.

Build agentic applications that leverage CockroachDB's distributed AI capabilities on AWS. AI agents
require persistent memory that never fails; CockroachDB serves as the globally distributed,
always-on system for agentic memory — handling conversation history, embeddings, and transactional
data at scale.

### Timeline (all times Eastern)

| Phase | Window |
| --- | --- |
| **Submission Period** | June 30, 2026 (10:00 am) – **August 18, 2026 (5:00 pm)** |
| **Judging Period** | August 19, 2026 (10:00 am) – September 15, 2026 (5:00 pm) |
| **Winners Announced** | On or around September 21, 2026 (3:00 pm) |

### Prizes — $8,750 total

| Place | Award |
| --- | --- |
| **1st** | $5,000 USD · blog feature · swag |
| **2nd** | $2,500 USD · swag |
| **3rd** | $1,250 USD · swag |

### Required project requirements

Build an agentic application using CockroachDB as persistent memory on AWS, using **at least two**
CockroachDB tools and **at least one** AWS service.

| CockroachDB tools (≥ 2 required) | Continuum |
| --- | --- |
| Cloud Managed MCP Server | ✅ `agents/query_agent.py` — read-only, called by the app at runtime |
| Distributed Vector Indexing | ✅ `incident_embeddings` C-SPANN index, live correlation queries — **6.1× faster than a full scan at 10,000 vectors**, with the query plan pinned by an integration test |
| ccloud CLI (Agent-Ready) | ❌ evaluated and deliberately cut — see ADR 004 |
| Agent Skills Repo (Open Source) | ❌ not used |

| AWS services (≥ 1 required) | Continuum |
| --- | --- |
| Bedrock | ✅ Titan Text Embeddings V2 + Claude Sonnet 4.5 |
| Lambda | ✅ orchestrator execution, no provisioned concurrency |
| ECS/EKS · S3 · SageMaker · others | ❌ not used |

### Required submission materials

- Public open-source repository with README, dependencies, configurations, and setup instructions,
  with a **detectable open-source license**
- Functional demo app URL
- Video demonstrating the submission **and the memory layer** — under 3 minutes, YouTube/Vimeo
- Documentation identifying which CockroachDB and AWS tools were used
- *Optional:* architecture diagram, and feedback on CockroachDB AI tools

### Eligibility rules that shaped this build

- **"Projects must be newly created by the Entrant during the Submission Period."** No pre-existing
  code was incorporated into Continuum.
- AI coding assistants are explicitly permitted; any pre-existing code must be disclosed. Continuum
  was built with **Claude Code** — disclosed in the README.

Tracking checklist: [`SUBMISSION.md`](SUBMISSION.md)

---

## Judging Alignment

The five criteria are **equally weighted**. Official descriptions quoted, followed by how Continuum
answers each.

| Criterion | Official description | How Continuum addresses it |
| --- | --- | --- |
| **Agentic Memory Design** | *"Whether CockroachDB meaningfully functions as production-grade memory layer"* | Dual memory in **one** CockroachDB store — ACID incident/remediation state *and* vector embeddings — not a toy chat log. Each step's checkpoint is an explicit `SERIALIZABLE` transaction, so a resuming invocation never reads a half-written state transition, and a forward step is claimed exactly once (`ON CONFLICT DO NOTHING`) even under concurrent invocations. |
| **Technical Implementation** | *"Quality software engineering and correct tool usage"* | Distributed Vector Indexing doing real correlation work; MCP Server as a live read-only query surface the app itself calls; a single-write-path Memory Agent enforced by convention and tests; recovery semantics pinned by CI — 53 unit tests (100% measured coverage against a 90% gate), plus integration tests driving the resume-and-exactly-once contract against a live CockroachDB instance rather than mocks. One (`test_chaos_kill_e2e.py`) hard-kills a real orchestrator subprocess mid-step with a genuine `SIGKILL` and asserts exactly-once cold recovery — the same script that drives the kill beat in the demo. |
| **Real-World Impact** | *"Meaningful use case and potential user value"* | Every engineering org runs production incidents. MTTR reduction from precedent-based remediation is directly measurable, not hypothetical — and the failure mode Continuum solves (the agent dying mid-incident) is one on-call engineers actually hit. |
| **Production Readiness** | *"Security, observability, scalability, and resilience"* | The kill-and-resume beat *is* the resilience proof, not a slide about it — and it's measured, not asserted: **50 interrupted incidents, 50 clean resumes, 0 duplicated actions, 0 lost steps**, plus **15 invocations killed by AWS itself** via Lambda timeout (no catchable signal, no chance to checkpoint) all recovering exactly once, and **0 exactly-once violations across 100 trials up to 50-way concurrency**. Full method and raw evidence: [`docs/RESILIENCE.md`](../docs/RESILIENCE.md), `assets/resilience-run/`. structlog JSON logging throughout; secrets via environment only; least-privilege IAM; lint, format, type, and coverage gates in CI; explicit scope cuts documented in ADR 006 rather than hidden. |
| **Creativity & Originality** | *"Novel ideas or applications demonstrating agentic system insights"* | A literal, load-bearing answer to the hackathon's own framing — an agent whose memory goes offline doesn't degrade gracefully, it stops — built as the single demo beat rather than a footnote. |

---

## Elevator Pitch

> An autonomous incident-response agent that resumes the exact step it was killed on: kill the process mid-remediation, and the next cold invocation picks up the interrupted step from CockroachDB — not from scratch, and never a duplicate. Its memory lives in the database, not the process.

---

## Project Story

### Inspiration

Most agentic-memory demos store chat history and call it a day. But the conditions that cause real production incidents — resource exhaustion, node failure, deploy rollbacks, autoscaling churn — are exactly the conditions that kill the agent responding to them. The hackathon brief said it directly: *"an agent whose memory goes offline doesn't degrade gracefully, it stops."* Continuum is built as a direct, literal test of that failure mode, not a workaround for it.

### What it does

A synthetic alert fires. The Orchestrator (designed for AWS Lambda, deliberately never kept warm) reads CockroachDB **first, before any new reasoning** — recovering any open incident matching this alert. The Correlation Agent embeds the alert via Amazon Bedrock (Titan v2) and searches CockroachDB's native vector index for similar past incidents. The Remediation Agent proposes the next action, reasoning over the matched precedent via Claude on Bedrock (best-effort — a red Bedrock endpoint degrades correlation to "no precedent" rather than aborting the incident). Each step commits in two explicit `SERIALIZABLE` transactions — the proposed action and `executing` status together, then `executed` — with the `time.sleep` execution window between them. Kill the process mid-step (`chaos_kill.py`, no graceful shutdown), and the next cold invocation finds the step frozen in `executing` and **re-runs that exact step** — no restart from scratch, no duplicated work, no lost context.

### How we built it

Five agents, one write path: `orchestrator.py` (recovery-read-first control flow), `correlation_agent.py` (Bedrock embeddings + CockroachDB vector search), `remediation_agent.py` (Claude-on-Bedrock reasoning with a deterministic precedent-replay fallback), `memory_agent.py` — the *only* module permitted to write `incidents` or `remediation_steps`, so a resuming invocation can trust everything it reads — and `query_agent.py`, a real MCP client (official `mcp` SDK) that calls the CockroachDB Cloud Managed MCP Server's read-only SQL tool at runtime, exposed through `GET /api/v1/incidents/open` and the Gradio UI. The schema unifies transactional and vector memory in one CockroachDB store: `incidents` and `remediation_steps` under `SERIALIZABLE` isolation, `incident_embeddings` with a `service`-prefixed C-SPANN vector index.

### Challenges we ran into

**A demo that wasn't actually testing what it claimed.** The first version of the chaos-kill demo fired one alert to completion, then killed an unrelated idle process and fired a second alert — the "resume" only looked correct because the first run had already finished. We redesigned the remediation loop so each step has a real, interruptible execution window (`STEP_EXECUTION_SECONDS`), with the status committed to CockroachDB *before* execution starts — so a kill genuinely lands mid-step, and the fix is provable, not just claimed.

**Titan v2's dimension ceiling.** The initial schema assumed 1536-dim embeddings (an OpenAI-shaped assumption); Amazon Titan Text Embeddings V2 tops out at 1024. Caught before it became a runtime surprise — `VECTOR(1024)` throughout, with `embedding_dimensions` centralized in config so schema and embedding calls can't drift apart again.

**Cross-platform chaos.** The original kill script only worked on POSIX (`lsof` + `kill -9`). Rewritten on `psutil` so the same script — and a native `chaos_demo.ps1` for Windows — works everywhere the demo gets recorded.

### Accomplishments that we're proud of

- A resilience guarantee that's actually exercised end-to-end by CI — 53 unit tests pin the exact recovery semantics (read-before-write, transactional step checkpoints, re-execute-if-interrupted, claim-exactly-once-under-concurrency, resolve-after-final-step), and integration tests run that same contract against a real CockroachDB instance CI provisions on every push — one of them literally hard-killing a live orchestrator subprocess mid-step and asserting it resumes exactly once — not just asserted in a README
- One CockroachDB store doing double duty as both the transactional system of record and the vector index, with a single statement that filters on structured columns *and* ranks by `<->` distance
- Recovery proven under failure modes we don't control — including **AWS terminating the Lambda mid-step**, where nothing in the process gets a signal or a chance to checkpoint, and the next cold invocation still resumes that exact step exactly once
- Catching that our own headline CockroachDB integration wasn't running. The correlation query joined `incidents` in the same statement as the `<->` ordering, which made the planner fall back to `spans: FULL SCAN` — **results stayed correct, so nothing failed and nothing looked wrong**, while "Distributed Vector Indexing" was a load-bearing claim in this submission. It surfaced only because a scale benchmark produced the wrong *shape* of curve. Fixed with a CTE, and pinned by an integration test that reads the query plan, plus a second test that fails deliberately if a future CockroachDB version makes the workaround unnecessary
- A demo script honest enough to admit its own earlier bug and fix the root cause instead of hiding it

### What we learned

- "The demo shows recovery" and "the demo can only show recovery" are very different claims — the second one requires the interrupted step to genuinely be mid-flight when the kill lands, which means designing the execution window *first*, not bolting timing onto an existing flow
- CockroachDB's PostgreSQL-compatible vector support (`<->` distance, native `VECTOR` columns) means the correlation query is ordinary SQL — no separate vector store, no consistency gap to design around
- A single-write-path convention (one module, one set of write functions) is cheap to establish early and expensive to retrofit once other code has started writing directly to the tables
- **A green test suite proves a query is correct, never that it is using the index you think it is.** Only `EXPLAIN` does. A correctness test and a performance test can both pass while the feature you're claiming sits idle, which is why the query plan is now asserted rather than assumed
- **Benchmark against a baseline you deliberately made slow.** The full-scan comparison is what turned an absolute latency number — unfalsifiable on its own — into a *shape*, and the shape is what exposed the bug. Related: measure warm and cold connections separately, or a ~340 ms TLS handshake floor silently buries whatever you were trying to measure

### What's next for Continuum

- Real alert-source integrations (PagerDuty/Opsgenie webhook ingestion) in place of the synthetic stream
- Multi-region incident correlation via `REGIONAL BY ROW` incident tables
- ccloud CLI backup/replication verification as a standing pre-flight check, not just a chaos-demo gate
- Slack/Teams remediation-approval loop before a proposed step executes

### Built with

Python, FastAPI, psycopg 3, CockroachDB Cloud (Distributed Vector Indexing, Managed MCP Server), Amazon Bedrock (Titan Text Embeddings V2, Claude), AWS Lambda, Gradio, Hugging Face Spaces, structlog, pytest, Ruff

---

## CockroachDB Tools Used

| Tool | What the agent actually does with it |
| --- | --- |
| **Distributed Vector Indexing** | `incident_embeddings.embedding VECTOR(1024)` with a C-SPANN index prefixed by `service`; the Correlation Agent's live query filters by structured columns *and* ranks by `<->` distance in one round trip |
| **CockroachDB Cloud Managed MCP Server** | Read-only mode; `agents/query_agent.py` is the app's own MCP client (official `mcp` SDK, streamable HTTP) — `GET /api/v1/incidents/open` and the Gradio UI's "Ask via MCP" button run live questions ("open incidents and their current step") through the protocol at runtime, not only via Claude Code during development |

ccloud CLI was evaluated and intentionally not included — see ADR 004's resolution: two tools done well outscores three done thin.

## AWS Services Used

| Service | What the agent actually does with it |
| --- | --- |
| **AWS Lambda** | Orchestrator execution on the `python3.14` runtime; deliberately no provisioned concurrency, so every invocation proves state comes from CockroachDB, not warm process memory (ADR 002) |
| **Amazon Bedrock** | Titan Text Embeddings V2 for alert→vector (1024-dim, matching the `VECTOR(1024)` schema); Claude Sonnet 4.5 for remediation reasoning over matched precedent, with a deterministic precedent-replay fallback so the control flow demos even when throttled |
| **AWS SAM** | Infrastructure as code for the orchestrator function ([`infra/template.yaml`](../infra/template.yaml)) — the absence of `ProvisionedConcurrencyConfig` is a deliberate, reviewable artifact rather than a console setting |
| **AWS IAM** | Least privilege: the application's credentials are scoped to Bedrock model invocation only and cannot list, create, or delete AWS resources. Budget guardrails attach a deny-all policy at the spend ceiling — see [`COSTS.md`](COSTS.md) |
