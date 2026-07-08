# Benchmarks

Latency of the CockroachDB memory operations the recovery guarantee depends on.
Reproduce with `make benchmark` (or `python scripts/benchmark.py --n 50`) against
your own cluster — numbers vary with cluster tier, region, and client distance.

**Run:** 2026-07-08 19:41 UTC · **Iterations:** 50 · **Vector search:** deterministic synthetic
vectors (no Bedrock) · **Measured from:** developer workstation over the public internet -> CockroachDB Cloud free-tier (Serverless), eu-central-1; fresh connection per call

| Operation | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) |
| --- | --- | --- | --- | --- |
| recovery read (get_open_incident) | 387.18 | 694.43 | 726.41 | 456.55 |
| vector search (find_similar, k=5) | 423.43 | 689.26 | 765.86 | 460.98 |
| step-start commit (checkpoint_step_start) | 417.35 | 688.22 | 728.28 | 455.14 |
| step-done commit (checkpoint_step_done) | 377.95 | 644.23 | 787.86 | 413.30 |
| end-to-end resume (recovery read + re-run step) | 1181.47 | 1776.16 | 2183.93 | 1277.52 |

Notes:
- `end-to-end resume` is the money metric: recovery read of the interrupted step
  plus re-running and committing it — the full cold-resume path a killed agent pays.
- `find_similar` is CockroachDB's C-SPANN ANN search (`service` filter + `<->` rank).
- Measured client-side (`time.perf_counter`) around each call, so it includes the
  round trip and commit, not just server execution.
- **These are measured from a developer machine, not the deployed Lambda.** Absolute
  latency is dominated by per-call connection setup (TLS + Serverless routing) over the
  public internet — each call opens a fresh connection, matching the Lambda's cold
  per-invocation pattern. The orchestrator Lambda is co-located with the cluster in
  eu-central-1 (ADR 007), so production per-call latency is expected to be substantially
  lower. Read the *relative* cost between operations (end-to-end resume ≈ 3× a single
  commit) as the durable signal, not the absolute milliseconds.
