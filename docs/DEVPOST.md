# Devpost Submission — Continuum

Hackathon: [CockroachDB × AWS Hackathon 2026](https://cockroachdb-ai.devpost.com/)
Submission Period: **June 30 – August 18, 2026 (5 PM ET)** · Judging: **Aug 19 – Sep 15** · Winners: ~Sep 21

> Per the [official rules](https://cockroachdb-ai.devpost.com/rules): public open-source repo with an
> OSS license visible in the About section; functional demo URL free to test through the Judging
> Period; demo video **< 3 minutes**, public on YouTube/Vimeo, showing the CockroachDB memory layer
> at work; explicit list of which CockroachDB tools and AWS services were used and how.

---

## Judging Alignment

| Criterion | How Continuum Addresses It |
| --- | --- |
| **Agentic Memory Design** | Dual memory in **one** CockroachDB store — ACID incident/remediation state *and* vector embeddings — not a toy chat log. `SERIALIZABLE` isolation guarantees a resuming invocation never reads a half-written state transition. |
| **Technical Implementation** | Distributed Vector Indexing doing real correlation work, MCP Server as a live read-only query surface, a single-write-path Memory Agent enforced by convention and tests, recovery semantics pinned by CI (5 unit tests assert read-before-write ordering, interrupted-step re-execution, and resolve-after-final-step). |
| **Real-World Impact** | Every engineering org runs production incidents; MTTR reduction from precedent-based remediation is directly measurable, not a hypothetical use case. |
| **Product Readiness** | The kill-and-resume beat *is* the readiness proof, not a slide about it. structlog JSON logging throughout; secrets via environment only; explicit scope cuts documented in ADR 006 instead of hidden. |
| **Creativity & Originality** | A literal, load-bearing answer to the hackathon's own brief — *"an agent whose memory goes offline doesn't degrade gracefully, it stops"* — built as the single demo beat rather than a footnote. |

---

## Elevator Pitch

> An incident-response agent whose memory survives the very outage it's diagnosing — kill the process mid-remediation, and the next cold invocation resumes the exact interrupted step from CockroachDB, not from scratch.

---

## Project Story

### Inspiration

Most agentic-memory demos store chat history and call it a day. But the conditions that cause real production incidents — resource exhaustion, node failure, deploy rollbacks, autoscaling churn — are exactly the conditions that kill the agent responding to them. The hackathon brief said it directly: *"an agent whose memory goes offline doesn't degrade gracefully, it stops."* Continuum is built as a direct, literal test of that failure mode, not a workaround for it.

### What it does

A synthetic alert fires. The Orchestrator (designed for AWS Lambda, deliberately never kept warm) reads CockroachDB **first, before any new reasoning** — recovering any open incident matching this alert. The Correlation Agent embeds the alert via Amazon Bedrock (Titan v2) and searches CockroachDB's native vector index for similar past incidents. The Remediation Agent proposes the next action, reasoning over the matched precedent via Claude on Bedrock. Every transition — `proposed → executing → executed` — is committed before and after it happens. Kill the process mid-step (`chaos_kill.py`, no graceful shutdown), and the next cold invocation finds the step frozen in `executing` and **re-runs that exact step** — no restart from scratch, no duplicated work, no lost context.

### How we built it

Four agents, one write path: `orchestrator.py` (recovery-read-first control flow), `correlation_agent.py` (Bedrock embeddings + CockroachDB vector search), `remediation_agent.py` (Claude-on-Bedrock reasoning with a deterministic precedent-replay fallback), and `memory_agent.py` — the *only* module permitted to write `incidents` or `remediation_steps`, so a resuming invocation can trust everything it reads. The schema unifies transactional and vector memory in one CockroachDB store: `incidents` and `remediation_steps` under `SERIALIZABLE` isolation, `incident_embeddings` with a `service`-prefixed C-SPANN vector index. The CockroachDB Cloud Managed MCP Server gives a live, read-only query surface into the same cluster from Claude Code during development and the demo.

### Challenges we ran into

**A demo that wasn't actually testing what it claimed.** The first version of the chaos-kill demo fired one alert to completion, then killed an unrelated idle process and fired a second alert — the "resume" only looked correct because the first run had already finished. We redesigned the remediation loop so each step has a real, interruptible execution window (`STEP_EXECUTION_SECONDS`), with the status committed to CockroachDB *before* execution starts — so a kill genuinely lands mid-step, and the fix is provable, not just claimed.

**Titan v2's dimension ceiling.** The initial schema assumed 1536-dim embeddings (an OpenAI-shaped assumption); Amazon Titan Text Embeddings V2 tops out at 1024. Caught before it became a runtime surprise — `VECTOR(1024)` throughout, with `embedding_dimensions` centralized in config so schema and embedding calls can't drift apart again.

**Cross-platform chaos.** The original kill script only worked on POSIX (`lsof` + `kill -9`). Rewritten on `psutil` so the same script — and a native `chaos_demo.ps1` for Windows — works everywhere the demo gets recorded.

### Accomplishments that we're proud of

- A resilience guarantee that's actually exercised end-to-end by CI (5 unit tests pin the exact recovery semantics: read-before-write, re-execute-if-interrupted, resolve-after-final-step) — not just asserted in a README
- One CockroachDB store doing double duty as both the transactional system of record and the vector index, with a single query joining structured filters and semantic ranking
- A demo script honest enough to admit its own earlier bug and fix the root cause instead of hiding it

### What we learned

- "The demo shows recovery" and "the demo can only show recovery" are very different claims — the second one requires the interrupted step to genuinely be mid-flight when the kill lands, which means designing the execution window *first*, not bolting timing onto an existing flow
- CockroachDB's PostgreSQL-compatible vector support (`<->` distance, native `VECTOR` columns) means the correlation query is ordinary SQL — no separate vector store, no consistency gap to design around
- A single-write-path convention (one module, one set of write functions) is cheap to establish early and expensive to retrofit once other code has started writing directly to the tables

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
| **CockroachDB Cloud Managed MCP Server** | Read-only mode; live questions ("open incidents and their current step") run through Claude Code against the cluster during development and the demo's query-interface beat |
| **ccloud CLI** *(stretch)* | Scripted backup/replication health check as the chaos-demo pre-flight — memory you can't verify isn't memory (ADR 004) |

## AWS Services Used

| Service | What the agent actually does with it |
| --- | --- |
| **AWS Lambda** | Orchestrator execution; deliberately no provisioned concurrency, so every invocation proves state comes from CockroachDB, not warm process memory (ADR 002) |
| **Amazon Bedrock** | Titan Text Embeddings V2 for alert→vector; Claude for remediation reasoning over matched precedent, with a deterministic precedent-replay fallback so the control flow demos even when throttled |
