# Continuum — Architecture

## 1. Problem Framing

Incident-response agents are typically demoed as stateless request/response loops: alert comes in, LLM reasons, suggestion goes out. That pattern quietly assumes the agent process stays alive for the duration of the incident. In real production environments, that assumption is exactly backwards — the conditions that cause incidents (resource exhaustion, node failure, deploy rollbacks, autoscaling churn) are the same conditions that can kill the agent process itself.

Continuum's design constraint: **the agent's own execution environment is allowed to die mid-incident. Its memory is not.**

This is why CockroachDB is the memory layer rather than an implementation detail — it is the mechanism that makes the constraint achievable.

|  | Typical "agent memory" demo | Continuum |
| --- | --- | --- |
| **What is stored** | Chat history / conversation buffer | Live remediation state — *which step is `executing` right now* |
| **Where it lives** | Process memory, or a cache that assumes the process survives | CockroachDB, committed before *and* after every step |
| **On process death mid-task** | State lost — restart from scratch or human re-input | Next cold invocation reads durable state and resumes the exact step |
| **Consistency model** | Best-effort | `SERIALIZABLE`, with an exactly-once step claim |
| **Failure the demo proves** | (usually untested) | Kill the agent mid-incident — recovery is the headline beat |

---

## 2. Memory Model

Continuum uses **one store for two kinds of memory**, deliberately, rather than pairing a vector DB with a separate operational DB:

### 2.1 Transactional memory — incident + remediation state

```
incidents            — one row per incident, current lifecycle state
remediation_steps    — append-only log of proposed/executed actions per incident
```

State transitions (`open → correlating → remediating → resolved | escalated`) are written with **explicit** CockroachDB transactions (psycopg `conn.transaction()`). Each remediation step is two such transactions — `checkpoint_step_start` (incident → `remediating` + the step claimed as `executing`) and `checkpoint_step_done` (the step → `executed`, plus `resolved` on the final step) — with the execution window between them. CockroachDB's default `SERIALIZABLE` isolation means a recovering Lambda invocation can never read a half-written state transition: it either sees the last fully-committed step, or it doesn't see it yet. There is no "memory went stale mid-write" failure mode to design around. See ADR 009 for the exactly-once claim guard.

### 2.2 Semantic memory — incident embeddings

```
incident_embeddings  — embedding per incident, VECTOR(1024), C-SPANN vector index
```

New alerts are embedded (via AWS Bedrock) and matched against this table using CockroachDB's native vector search (`<->` L2 distance / `<=>` cosine distance operators — pgvector-compatible syntax). Because the embedding lives in the same distributed SQL engine as the transactional state, a single query can filter by structured fields (service, severity, region) *and* rank by semantic similarity in one round trip — no separate vector store to keep in sync, no consistency gap between "what the agent knows" and "what actually happened."

See [`infra/schema.sql`](../infra/schema.sql) for the exact DDL.

---

## 3. The Recovery Guarantee (Production Readiness proof)

This is the core resilience mechanic and the centerpiece of the demo video. Two cold Lambda invocations — the second with no shared memory with the first — hand off entirely through durable CockroachDB state:

```mermaid
sequenceDiagram
    autonumber
    participant Al as 🚨 Alert stream
    participant A as ⚡ Lambda A (cold)
    participant DB as 🪳 CockroachDB
    participant K as 💀 chaos_kill.py
    participant B as ⚡ Lambda B (cold)

    Al->>A: alert (correlation_id)
    A->>DB: recovery read FIRST — no open incident
    A->>DB: open incident + checkpoint_step_start(step 0)
    Note over DB: step 0 committed 'executing'<br/>(SERIALIZABLE, before execution)
    A-->>A: execute step 0 (sleep window)
    K-->>A: SIGKILL — no graceful shutdown
    Note over A,DB: process gone — step 0 still durably 'executing'
    Al->>B: next tick — same correlation_id
    B->>DB: recovery read FIRST — finds step 0 'executing'
    B-->>B: re-run step 0 (not skipped, not duplicated)
    B->>DB: checkpoint_step_done(step 0) → 'executed'
    Note over DB: exactly-once preserved; state outlived the process
```

The same flow, step by step:

```
1. Alert fires → Lambda invocation A starts
2. A's FIRST action: recovery read — no open incident yet, so open one
3. Correlation Agent embeds alert, queries incident_embeddings → finds precedent
   (best-effort — a Bedrock outage degrades to "no precedent", it does not abort)
4. Memory Agent checkpoint_step_start commits ONE SERIALIZABLE transaction:
   incidents.state = 'remediating' + remediation_steps[0] claimed as 'executing'
   (a forward step is claimed exactly once — INSERT ... ON CONFLICT DO NOTHING)
5. [chaos_kill.py terminates the process here — inside the execution window]
   → step[0] is durably 'executing', never advanced to 'executed'
6. New alert-stream tick → Lambda invocation B starts — cold, no shared memory with A
7. B's FIRST action is always: read incidents + the latest remediation_steps row
   for any open incident matching this alert's correlation_id
8. B finds step[0] status = 'executing' (incomplete) → RE-RUNS step[0], does not
   skip to step[1], does not open a second incident. checkpoint_step_done then
   commits step[0] = 'executed'. (Had step[0] been fully 'executed', B would
   instead advance to step[1] — never re-running a completed step.)
```

Nothing about step 7 is optional or best-effort — it's the first branch in `orchestrator.py`, before any new reasoning happens. This is what separates Continuum from "an agent that also happens to log to a database."

---

## 4. CockroachDB Tool Usage — Detail

### 4.1 Distributed Vector Indexing
- Table: `incident_embeddings(incident_id, service, region, embedding VECTOR(1024), embedding_model, created_at)` — 1024 matches Amazon Titan Text Embeddings V2's max output dimension
- Index: `CREATE VECTOR INDEX ON incident_embeddings (service, embedding);` — prefixed by `service` so the ANN search is naturally partitioned per-service rather than scanning the full cross-service corpus (the same way CockroachDB partitions per-tenant in its own reference examples)
- Query pattern: filter by `service`, order by `embedding <-> $query_vector`, `LIMIT k` — structured filter and semantic rank in one round trip (`agents/correlation_agent.py`)

### 4.2 CockroachDB Cloud Managed MCP Server
- Used in **read-only mode** (the server's default safe mode)
- `agents/query_agent.py` is a real client of the server — official `mcp` Python SDK, streamable HTTP transport, calling its read-only SQL tool at runtime. This is invoked from `GET /api/v1/incidents/open` and the Gradio UI's "Ask via MCP" button, so the *running application* uses MCP, not only Claude Code/Cursor during development (see ADR 003's update)
- Example queries: *"list all open incidents"*, *"show remediation history for incident X"*, *"which past incidents correlate with this one"*
- Audit logging on the MCP server itself doubles as a lightweight compliance trail for "what did the agent actually look at"

CockroachDB tool count stops at two (Vector Indexing + MCP Server) by design — see ADR 004's resolution on why ccloud CLI was evaluated and cut rather than added as a thinner third integration.

---

## 5. AWS Usage — Detail

- **AWS Lambda** — the orchestrator runs as a Lambda function, invoked per alert-stream tick. Explicitly *not* provisioned-concurrency / kept-warm, so each demo run genuinely tests cold recovery rather than reusing warm in-memory state.
- **Amazon Bedrock** — one model for embeddings (alert → vector), one for remediation reasoning (candidate action generation given correlated precedent).

---

## 6. Explicit Non-Goals (Scope Discipline)

To keep this buildable solo within the submission window:

- No real alerting integration (PagerDuty/Opsgenie) — a synthetic, deterministic alert stream instead
- No real production infrastructure being monitored — synthetic service/incident corpus only
- No multi-region deployment in the MVP — the schema is written to support it (`region` columns, prefix-partitioned vector index) but only single-region is demoed
- No fine-grained RBAC beyond what the MCP Server provides by default — noted as roadmap, not claimed as built

These cuts are documented, not hidden — see [`docs/adr/006-scope-cuts.md`](adr/006-scope-cuts.md).
