# Resilience Benchmarks

`BENCHMARKS.md` answers *how fast*. This answers the question Continuum exists to
answer: **when the agent dies mid-incident, does it resume exactly once — every
time, under contention, at scale?**

**Run:** 2026-08-07 13:06 UTC · **Code:** `a142475` · Reproduce with `make resilience-bench`.

<sub>The commit is recorded because a benchmark outlives the code it measured. An
earlier version of this file published a vector-search table generated *before*
`find_similar` was fixed to actually use the C-SPANN index — the numbers were
meaningless and nothing on the page said so. If the commit above predates a change
to what is being measured, treat the numbers as stale and re-run.</sub>

### Provenance — derived, not asserted

> **Re-rendered from committed evidence measured at `a142475`.** That run's manifest predates per-file provenance, so it records only a single dirty flag — not which files. That flag counted **untracked** files too, and a run's own evidence folder is untracked while it is being written, so every run of that vintage reported dirty; it is not evidence that measured code was uncommitted. The numbers below are the ones it captured; the commit is the one it captured them at.

---

## A. Kill storm

**50 interrupted incidents. 50 clean resumes. 0 duplicated remediation actions. 0 lost steps.**

### A1 — injected interrupt (large N)

Each incident is advanced a random number of steps, then left with a step durably
`executing` — the exact fingerprint a `SIGKILL` mid-step leaves in CockroachDB —
and then invoked cold. This is an *injected* interrupt, not a signal: it measures
the same recovery contract without paying a process spawn per sample.

| Interrupted | Resumed | Duplicated actions | Lost steps | Resumed at wrong step |
| --- | --- | --- | --- | --- |
| 50 | 50 | 0 | 0 | 0 |

Cold resume latency: p50 **6582 ms**,
p95 **6638 ms**,
p99 **6738 ms** (n=50).

**Each of those figures includes a fixed 5.0 s simulated
execution window** — the `sleep` a real kill strikes inside — so the recovery work itself is
p50 ≈ **1582 ms**.
Stated because the window is a run parameter, not a property of the system: a run at a different
window produces a different-looking latency for identical recovery behaviour, and comparing the two
without this line would read as a speed-up that never happened.

*Duplicated actions* is the one that matters operationally: re-running a remediation
step can be worse than never running it. It is counted by reading the durable row
back, not inferred from the return value.

### A2 — real `SIGKILL` of a live orchestrator process

The genuine article: a uvicorn server is spawned, an alert fired, and the process
hard-killed mid-step by `scripts/chaos_kill.py` — no graceful shutdown, no cleanup
handler. Small N by design; each sample costs a process spawn.

| Kills | Resumed correctly | Duplicated steps | Lost steps | Setup failures |
| --- | --- | --- | --- | --- |
| 10 | 10 | 0 | 0 | 0 |

Resume latency after a real kill: p50 **6550 ms**,
p95 **6588 ms** (n=10).

### A3 — AWS kills the function (Lambda timeout)

The strongest form of this evidence, because **we did not perform the kill**.
The deployed function's `Timeout` was lowered to **6s** — below the
step-execution window — so Lambda terminated the invocation mid-step with no
catchable signal and no cleanup. The original timeout (60s) is
restored in a `finally`.

| Invocations | Killed by AWS | Resumed correctly | Duplicated steps | Not interrupted |
| --- | --- | --- | --- | --- |
| 15 | 15 | 15 | 0 | 0 |

Resume latency after an AWS-initiated kill: p50 **9038 ms**,
p95 **9787 ms** (n=15).

Every timed-out invocation resumed exactly once.

---

## B. Exactly-once under concurrency

K invocations race `checkpoint_step_start` on the **same** `(incident_id, step_index)`.
ADR 009 makes the forward claim exactly-once with `INSERT ... ON CONFLICT DO NOTHING`;
exactly one caller may win, the rest must be told to stand down.

| Concurrency | Trials | Claimed | Correctly skipped | **Violations** |
| --- | --- | --- | --- | --- |
| 2 | 20 | 1 | 1 | 0 |
| 5 | 20 | 1 | 4 | 0 |
| 10 | 20 | 1 | 9 | 0 |
| 25 | 20 | 1 | 24 | 0 |
| 50 | 20 | 1 | 49 | 0 |

**Zero violations at every concurrency level.** A second claimant would mean a remediation action executing twice — the failure this guard exists to prevent.

---

## B2. Concurrent agent throughput

Suite B asks whether contention stays *correct*. This asks whether the memory
layer *holds up*. Each simulated agent owns its own incident and drives a full
two-phase checkpoint (`open_incident` → `checkpoint_step_start` →
`checkpoint_step_done`) on its own connection, as a real agent would.

**Scope, stated so the number isn't over-read:** this measures the CockroachDB
memory layer under concurrent agents — deliberately no Bedrock and no execution
window, because those are third-party latency and a `sleep`, and including them
would measure Amazon rather than the database. "N completed/s" means N agents
completing their memory operations per second, not N full incidents resolved.

| Agents | Completed/s | p50 (ms) | p95 (ms) | wall (s) | Failures |
| --- | --- | --- | --- | --- | --- |
| 10 | 8.9 | 1109 | 1116 | 1.1 | 0 |
| 50 | 34.8 | 1372 | 1424 | 1.4 | 0 |
| 100 | 53.7 | 1699 | 1810 | 1.9 | 0 |

**Zero failures at every level.** Per-agent latency rising while throughput climbs is the expected shape: the cluster is absorbing concurrency rather than rejecting it.

---

## C. Vector search at scale

A benchmark over a few dozen vectors proves nothing: at that size an ANN index, a
full scan and a Python loop are indistinguishable. This grows the corpus and
measures C-SPANN against a forced full scan (`@primary`) over the same data.

Measured two ways. **Warm** reuses one connection and isolates what the *query*
costs; **cold** opens a fresh connection per call, matching the Lambda's
per-invocation pattern. The cold columns carry a ~340 ms floor of TLS and
serverless routing over the public internet that has nothing to do with
indexing — reported because it is what production actually pays, but the warm
columns are where the index's behaviour is visible.

**These numbers were measured against a CockroachDB Cloud cluster.** The multiple
below is therefore a property of that deployment as well as of the index: on a
single-node local cluster the full scan it has to beat is far cheaper, so the same
correct behaviour yields a visibly smaller ratio. Reproducing this with
`make local-cluster` should be expected to narrow the gap, not to reproduce it.

| Vectors | C-SPANN warm p50 | full scan warm p50 | C-SPANN cold p50 | full scan cold p50 |
| --- | --- | --- | --- | --- |
| 100 | 43 | 40 | 367 | 368 |
| 1,000 | 61 | 79 | 394 | 409 |
| 5,000 | 76 | 309 | 405 | 617 |
| 10,000 | 77 | 582 | 417 | 979 |

Across a **100× larger corpus** (100 → 10,000 vectors), on a warm connection:

- **C-SPANN: 43 ms → 77 ms** (1.81×)
- **Full scan: 40 ms → 582 ms** (14.71×)
- At 10,000 vectors the index is **7.5× faster**, and the gap widens with every row added.

Both queries run against the same rows on the same connection, so the warm
comparison is like-for-like. `@primary` forces the full scan, which is the
baseline the index has to beat.

---

## D. Deploy mid-incident — the code replaced underneath an open step

Every suite above takes the *process* away. This one takes the **code** away, and it is the
failure an on-call engineer actually causes: shipping a fix while an incident is still open.

The drill holds an incident durably in `executing`, then runs a real `sam build` + `sam deploy`
from a clean clone against the deployed function, and invokes it cold afterwards. Nothing bridges
the two builds except the CockroachDB row.

**Run:** 2026-08-07 17:39 UTC · run id `dba642ed` · code `ae768ab` · `make deploy-restart-drill`

| Phase | Observed |
| --- | --- |
| Interrupt | AWS timed the invocation out (`Timeout` 6 s, restored to 60 s in a `finally`) |
| Durable after kill | step 0, `executing`, 1 row |
| Deploy | 48.6 s · `CodeSha256` `cfj/1z90…` → `r8pbqNx1…` · revision id changed |
| Cold resume | **same incident**, step 0 re-executed on the new build in 10834 ms |
| Duplication | **none** — 1 row for the step |

The resumed invocation returned `resumed: true`,
`reexecuted_after_interrupt: true`, and
`correlation_source` / `reasoning_source` both `bedrock` — so the new build ran the live AWS path,
not a fallback, while completing a step the *previous* build had started.

**The drill fails if the code did not actually change.** It compares `CodeSha256` before and after
and refuses to pass on a no-op deploy, which would otherwise report success while proving nothing.
`code_replaced: true` and `revision_changed: true` are asserted, not narrated.

**n=1, stated plainly.** Each sample costs a full `sam build` + `sam deploy` against the live
function, so this demonstrates that the contract holds across a code replacement — it is not a
distribution. Suites A–B carry the statistical weight. Raw evidence:
[`assets/deploy-restart-run/dba642ed/`](../assets/deploy-restart-run/dba642ed/).

<sub>Measured by `scripts/deploy_restart_drill.py`, not by this script, and rendered here from that
run's committed evidence. It used to be written into this file by hand, which meant the next
`make resilience-bench` deleted it — once, silently, for a whole release.</sub>

---

## How to read these honestly

- **A1 is an injected interrupt, A2 is a real signal.** A1 gives statistical weight;
  A2 gives authenticity. Neither alone is the whole claim, which is why both are here.
  `tests/integration/test_chaos_kill_e2e.py` runs the A2 flow in CI on every push.
- **Sizes are small on purpose.** This runs against a live CockroachDB Basic cluster.
  Raise them with `--kills`, `--real-kills`, `--max-vectors`.
- **Every suite cleans up after itself.** Rows are created under `resbench-*`
  correlation IDs and deleted in a `finally`.
- **Latency numbers here are dominated by connection setup**, as in `BENCHMARKS.md`.
  The correctness counts — duplicated, lost, violations — are the results that matter,
  and they are absolute rather than relative.
