# Benchmarks

What a remediation step actually costs, measured — not modelled. Reproduce with
`make benchmark`; numbers vary with cluster tier, region and client distance.

**Run:** 2026-08-01 18:48 UTC · **Vector search:** real Amazon Titan Text Embeddings V2 vectors

## 1. What this measures, and why

Continuum's claim is that an agent can be killed mid-incident and resume from
CockroachDB. That claim is only interesting if the memory layer is fast enough that
durability isn't paid for in latency. These are the operations on that path:

| Leg | What it is | Where it runs |
| --- | --- | --- |
| recovery read | `get_open_incident` — the first thing every invocation does (ADR 002) | CockroachDB |
| Titan embed | alert text → 1024-dim vector | Amazon Bedrock |
| vector search | C-SPANN ANN over `incident_embeddings`, `service` filter + `<->` rank | CockroachDB |
| step-start / step-done | the two `SERIALIZABLE` checkpoints a kill lands between (ADR 009) | CockroachDB |
| end-to-end resume | recovery read + re-run + commit — what a killed agent pays | CockroachDB |

## 2. On the deployed Lambda (the number that counts)

`continuum-orchestrator`, eu-central-1, in-region with the cluster, no provisioned
concurrency (ADR 002). Each `correlation_id` is invoked twice: once to open the
incident, once more so the second invocation *must* recover it from CockroachDB.

Every invocation includes a fixed `STEP_EXECUTION_SECONDS` sleep simulating the
remediation window `chaos_kill.py` strikes in — **subtract it to read the real work.**

| Operation | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | n |
| --- | --- | --- | --- | --- | --- |
| invocation — new incident (client round trip) | 7955.9 | 8097.2 | 8112.3 | 7825.0 | 5 |
| invocation — RESUMED from CockroachDB (client round trip) | 7678.9 | 7854.0 | 7861.2 | 7721.2 | 5 |
| Lambda-reported Duration — new incident | 7905.0 | 7980.3 | 7980.5 | 7759.4 | 5 |
| Lambda-reported Duration — resumed | 7635.4 | 7808.5 | 7816.7 | 7676.3 | 5 |
| cold-start init (Lambda Init Duration) | 1722.0 | 1773.7 | 1778.7 | 1720.5 | 4 |

**Resuming an incident and opening a new one cost the same.** 7676 ms vs 7759 ms mean — a 83 ms difference against 583 ms of spread within the samples themselves, i.e. indistinguishable at this sample size. The recovery read that makes a killed agent's memory survivable does not show up as a cost on the hot path: durability is bought by *where* the state lives, not by spending time re-establishing it.

- **client round trip** is measured from the invoking machine, so it carries public
  internet latency to the AWS API. **Lambda-reported Duration** is what the function
  itself billed, in-region. Compare the two to see the network cost, and compare
  Duration here against §3 to see what co-location buys.
- **What actually ran** (`correlation_source`/`reasoning_source`, counted not assumed): `bedrock/bedrock` ×15. A `no_precedent` reasoning source means the vector search found nothing and Claude was never called — those invocations measure a strictly cheaper path.
- **4 of 15 invocations paid a cold start.** Sequential calls reuse a warm execution environment, so the paired invocations above mostly skip init; the cold-start row comes from a separate batch fired *concurrently*, which forces Lambda to provision separate environments. ADR 002's claim is that no invocation may *depend* on warm state — not that AWS never supplies one — so both numbers are real and neither is the whole picture. The recovery path is exercised identically either way, since the first thing every invocation does is read CockroachDB.

## 3. CockroachDB memory operations, from a developer workstation

**Iterations:** 30 · **Measured from:** developer workstation (Nordics) over the public internet -> CockroachDB Cloud Basic (Serverless), eu-central-1; fresh connection per call

| Operation | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | n |
| --- | --- | --- | --- | --- | --- |
| Titan embed (Bedrock InvokeModel) | 107.7 | 134.7 | 318.9 | 115.4 | 30 |
| recovery read (get_open_incident) | 339.6 | 357.6 | 360.0 | 341.2 | 30 |
| vector search (find_similar, k=5) | 379.1 | 427.9 | 454.2 | 385.2 | 30 |
| step-start commit (checkpoint_step_start) | 379.2 | 394.0 | 401.6 | 380.1 | 30 |
| step-done commit (checkpoint_step_done) | 341.4 | 358.8 | 365.2 | 342.0 | 30 |
| end-to-end resume (recovery read + re-run step) | 1067.6 | 1099.4 | 1102.6 | 1067.4 | 30 |

- `end-to-end resume` is the money metric: recovery read of the interrupted step plus
  re-running and committing it.
- Measured client-side (`time.perf_counter`) around each call, so it includes the round
  trip and commit, not just server execution. Each call opens a fresh connection,
  matching the Lambda's cold per-invocation pattern.
- These absolute numbers are dominated by per-call TLS setup and Serverless routing over
  the public internet. Read the *relative* cost between operations as the durable signal,
  and §2 for what the same work costs in-region.

## Caveats worth stating plainly

- CockroachDB Basic (Serverless) scales to zero; a cluster that has been idle pays a
  routing cost on the first call that a provisioned cluster would not.
- Percentiles over 30 samples are indicative, not production SLO evidence.
- Bedrock quotas are dynamic and account-level (ADR 008). A throttled account degrades
  to deterministic fallbacks, which would make these numbers *faster* and less
  meaningful — the `reasoning_source` / `correlation_source` markers on every step are
  how you confirm a run actually exercised Bedrock.
