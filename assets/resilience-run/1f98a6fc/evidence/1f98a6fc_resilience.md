# Resilience Benchmarks

`BENCHMARKS.md` answers *how fast*. This answers the question Continuum exists to
answer: **when the agent dies mid-incident, does it resume exactly once — every
time, under contention, at scale?**

**Run:** 2026-08-02 10:17 UTC · Reproduce with `make resilience-bench`.

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

Cold resume latency: p50 **6584 ms**,
p95 **6679 ms**,
p99 **6801 ms** (n=50).

*Duplicated actions* is the one that matters operationally: re-running a remediation
step can be worse than never running it. It is counted by reading the durable row
back, not inferred from the return value.

### A2 — real `SIGKILL` of a live orchestrator process

The genuine article: a uvicorn server is spawned, an alert fired, and the process
hard-killed mid-step by `scripts/chaos_kill.py` — no graceful shutdown, no cleanup
handler. Small N by design; each sample costs a process spawn.

| Kills | Resumed correctly | Duplicated steps | Lost steps | Setup failures |
| --- | --- | --- | --- | --- |
| 3 | 3 | 0 | 0 | 0 |

Resume latency after a real kill: p50 **6563 ms**,
p95 **6604 ms** (n=3).

### A3 — AWS kills the function (Lambda timeout)

The strongest form of this evidence, because **we did not perform the kill**.
The deployed function's `Timeout` was lowered to **6s** — below the
step-execution window — so Lambda terminated the invocation mid-step with no
catchable signal and no cleanup. The original timeout (60s) is
restored in a `finally`.

| Invocations | Killed by AWS | Resumed correctly | Duplicated steps | Not interrupted |
| --- | --- | --- | --- | --- |
| 3 | 3 | 3 | 0 | 0 |

Resume latency after an AWS-initiated kill: p50 **8696 ms**,
p95 **8808 ms** (n=3).

Every timed-out invocation resumed exactly once.

---

## B. Exactly-once under concurrency

K invocations race `checkpoint_step_start` on the **same** `(incident_id, step_index)`.
ADR 009 makes the forward claim exactly-once with `INSERT ... ON CONFLICT DO NOTHING`;
exactly one caller may win, the rest must be told to stand down.

| Concurrency | Trials | Claimed | Correctly skipped | **Violations** |
| --- | --- | --- | --- | --- |
| 2 | 5 | 1 | 1 | 0 |
| 5 | 5 | 1 | 4 | 0 |
| 10 | 5 | 1 | 9 | 0 |
| 25 | 5 | 1 | 24 | 0 |

**Zero violations at every concurrency level.** A second claimant would mean a remediation action executing twice — the failure this guard exists to prevent.

---

## B2. Concurrent agent throughput

Suite B asks whether contention stays *correct*. This asks whether the memory
layer *holds up*. Each simulated agent owns its own incident and drives a full
two-phase checkpoint (`open_incident` → `checkpoint_step_start` →
`checkpoint_step_done`) on its own connection, as a real agent would.

| Agents | Completed/s | p50 (ms) | p95 (ms) | wall (s) | Failures |
| --- | --- | --- | --- | --- | --- |
| 10 | 8.8 | 1132 | 1134 | 1.1 | 0 |
| 50 | 34.8 | 1293 | 1398 | 1.4 | 0 |
| 100 | 47.4 | 1583 | 1873 | 2.1 | 0 |

**Zero failures at every level.** Per-agent latency rising while throughput climbs is the expected shape: the cluster is absorbing concurrency rather than rejecting it.

---

## C. Vector search at scale

A benchmark over a few dozen vectors proves nothing: at that size an ANN index, a
full scan and a Python loop are indistinguishable. This grows the corpus and
measures C-SPANN against a forced full scan (`@primary`) over the same data.

| Vectors | C-SPANN p50 (ms) | C-SPANN p95 (ms) | full scan p50 (ms) | full scan p95 (ms) |
| --- | --- | --- | --- | --- |
| 100 | 391 | 412 | 393 | 401 |
| 1,000 | 406 | 415 | 435 | 445 |
| 5,000 | 425 | 458 | 693 | 731 |
| 10,000 | 431 | 469 | 995 | 1056 |

The corpus grew **100×** (100 → 10,000 vectors) while ANN p50 moved **1.10×**. 
Both paths pay the same per-call connection setup over the public internet
(~340 ms floor, see `BENCHMARKS.md` §3), so read the *slope*, not the absolute
values: what matters is how each curve responds to corpus growth.

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
