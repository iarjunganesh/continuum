# Continuum — Architecture

## 1. Problem Framing

Incident-response agents are typically demoed as stateless request/response loops: alert comes in, LLM reasons, suggestion goes out. That pattern quietly assumes the agent process stays alive for the duration of the incident. In real production environments, that assumption is exactly backwards — the conditions that cause incidents (resource exhaustion, node failure, deploy rollbacks, autoscaling churn) are the same conditions that can kill the agent process itself.

Continuum's design constraint: **the agent's own execution environment is allowed to die mid-incident. Its memory is not.**

This is why CockroachDB is the memory layer rather than an implementation detail — it is the mechanism that makes the constraint achievable.

---

## 2. Memory Model

Continuum uses **one store for two kinds of memory**, deliberately, rather than pairing a vector DB with a separate operational DB:

### 2.1 Transactional memory — incident + remediation state

```
incidents            — one row per incident, current lifecycle state
remediation_steps    — append-only log of proposed/executed actions per incident
```

State transitions (`open → correlating → remediating → resolved | escalated`) are written with standard SQL transactions. CockroachDB's default `SERIALIZABLE` isolation means a recovering Lambda invocation can never read a half-written state transition — it either sees the last fully-committed step, or it doesn't see it yet. There is no "memory went stale mid-write" failure mode to design around.

### 2.2 Semantic memory — incident embeddings

```
incident_embeddings  — embedding per incident, VECTOR(1024), C-SPANN vector index
```

New alerts are embedded (via AWS Bedrock) and matched against this table using CockroachDB's native vector search (`<->` L2 distance / `<=>` cosine distance operators — pgvector-compatible syntax). Because the embedding lives in the same distributed SQL engine as the transactional state, a single query can filter by structured fields (service, severity, region) *and* rank by semantic similarity in one round trip — no separate vector store to keep in sync, no consistency gap between "what the agent knows" and "what actually happened."

See [`infra/schema.sql`](../infra/schema.sql) for the exact DDL.

---

## 3. The Recovery Guarantee (Product Readiness proof)

This is the core resilience mechanic and the centerpiece of the demo video.

```
1. Alert fires → Lambda invocation A starts
2. Correlation Agent embeds alert, queries incident_embeddings → finds precedent
3. Memory Agent writes incidents.state = 'remediating', logs remediation_steps[0]
4. [chaos_kill.py terminates the Lambda process here]
5. New alert-stream tick (or retry) → Lambda invocation B starts — cold, no shared memory with A
6. Orchestrator's FIRST action is always: read incidents.state + remediation_steps
   for any open incident matching this alert's correlation_id
7. B finds state = 'remediating', step[0] already logged
8. B resumes at step[1] — does not re-run step[0], does not lose context
```

Nothing about step 6 is optional or best-effort — it's the first branch in `orchestrator.py`, before any new reasoning happens. This is what separates Continuum from "an agent that also happens to log to a database."

---

## 4. CockroachDB Tool Usage — Detail

### 4.1 Distributed Vector Indexing
- Table: `incident_embeddings(incident_id, service, region, embedding VECTOR(1024), created_at)` — 1024 matches Amazon Titan Text Embeddings V2's max output dimension
- Index: `CREATE VECTOR INDEX ON incident_embeddings (embedding);` (optionally prefixed by `service` to partition the ANN search per-service, the same way CockroachDB partitions per-tenant in its own reference examples)
- Query pattern: filter by `service`/`region`, order by `embedding <-> $query_vector`, `LIMIT k`

### 4.2 CockroachDB Cloud Managed MCP Server
- Used in **read-only mode** (the server's default safe mode) for live inspection during development and for the demo's query-interface beat
- Example queries run through MCP during the demo: *"list all open incidents"*, *"show remediation history for incident X"*, *"which past incidents correlate with this one"*
- Audit logging on the MCP server itself doubles as a lightweight compliance trail for "what did the agent actually look at"

### 4.3 ccloud CLI
- Given a real, non-decorative job: scripted verification that cluster backups and cross-region replication are healthy, run as a pre-flight check before the chaos-kill demo. The narrative point: an incident-memory system that can't verify its own durability isn't trustworthy — this is that verification, not a checkbox integration.

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
