# Benchmarks

Latency of the CockroachDB memory operations the recovery guarantee depends on.
Reproduce with `make benchmark` (or `python scripts/benchmark.py --n 50`) against
your own cluster — numbers vary with cluster tier, region, and client distance.
Running it **regenerates this file** with your measured numbers.

**Run:** _not yet captured — run `make benchmark`_ · **Iterations:** 50 · **Vector
search:** deterministic synthetic vectors (no Bedrock) · **Cluster/region/client:**
_fill in for your run_

| Operation | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) |
| --- | --- | --- | --- | --- |
| recovery read (get_open_incident) | — | — | — | — |
| vector search (find_similar, k=5) | — | — | — | — |
| step-start commit (checkpoint_step_start) | — | — | — | — |
| step-done commit (checkpoint_step_done) | — | — | — | — |
| end-to-end resume (recovery read + re-run step) | — | — | — | — |

Notes:
- `end-to-end resume` is the money metric: recovery read of the interrupted step
  plus re-running and committing it — the full cold-resume path a killed agent pays.
- `find_similar` is CockroachDB's C-SPANN ANN search (`service` filter + `<->` rank).
- Measured client-side (`time.perf_counter`) around each call, so it includes the
  round trip and commit, not just server execution.
