# ADR 001: Single Store for Transactional + Vector Memory

## Status
Accepted

## Context
Incident data has two shapes: structured lifecycle state (which needs ACID guarantees — you cannot have two agents both think they're on remediation step 3) and semantic content (which needs similarity search against a corpus of past incidents). The common pattern is to split these across a relational DB and a dedicated vector store (Pinecone, Weaviate, pgvector-on-a-side-instance), synced via application code.

## Decision
Use CockroachDB for both, in the same schema, via its native `VECTOR` column type and C-SPANN vector index — no separate vector store.

## Consequences
- No sync lag or consistency gap between "what the agent has done" (transactional) and "what the agent has seen" (semantic) — a single query can join both
- One system to reason about for backup, replication, and access control, rather than two
- Directly exercises the hackathon's core thesis (CockroachDB as unified agentic memory) rather than using CockroachDB for state and a separate service for embeddings
- Trade-off: CockroachDB's vector indexing is a newer, preview-stage feature relative to mature dedicated vector DBs — acceptable for a hackathon-scale corpus (hundreds to low-thousands of incidents), flagged as a scaling consideration for real production volume
