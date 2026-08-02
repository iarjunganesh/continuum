# Roadmap

The single internal work-tracker for Continuum, ordered by how much each item
moves the hackathon judging criteria. Supersedes `HACKATHON_PRIORITIES.md` and
`DEMO_READINESS_CHECKLIST.md`, which tracked overlapping work and had already
begun to disagree with each other.

**Scope split, so this doesn't happen again:**

| Document | Audience | Owns |
| --- | --- | --- |
| **this file** | us | what's left to build, and why it matters |
| [`submission/SUBMISSION.md`](../submission/SUBMISSION.md) | judges | rules compliance + honestly-stated known gaps |
| [`CHANGELOG.md`](../CHANGELOG.md) | everyone | what shipped, when |

Everything below serves one claim:

> An AI agent can be killed mid-incident and resume exactly where it stopped,
> because its memory lives in CockroachDB rather than in the process.

**Status is evidence-graded, not aspirational.** ✅ means something was
measured or executed and can be pointed at. ⚠️ means partly done with the
remainder named. ❌ means not started. Nothing is ✅ on the strength of code
existing — the recurring lesson of this project is that code which has never
run is unproven, not proven-good.

---

## P0 — the submission depends on these

### 1. Never-Miss recovery benchmark ⭐ the centrepiece

Kill the agent by every plausible mechanism; prove it resumes exactly once.

| Failure mode | Status | Evidence |
| --- | --- | --- |
| Real `SIGKILL` mid-step | ✅ | `tests/integration/test_chaos_kill_e2e.py` in CI on every push; `scripts/resilience_bench.py --real-kills N` for statistical weight |
| Injected durable interrupt (large N) | ✅ | `resilience_bench.py` kill storm — the exact `executing` state a kill leaves |
| **Lambda timeout** | ❌ | The most compelling one and untested: AWS kills the function itself mid-step. Nobody can argue that was staged |
| **Container / execution-environment restart** | ❌ | Distinct from a process kill — the whole sandbox goes |
| **Deployment restart mid-incident** | ❌ | `sam deploy` while an incident is in flight |

Metrics already captured per run: resume latency (p50/p95/p99), duplicated
actions, lost steps, resumed-at-wrong-step. Correctness counts are absolute —
any non-zero value is a defect, not a percentile.

**Next:** the three ❌ rows. They complete the failure-mode matrix and are the
strongest evidence in the whole submission.

### 2. Concurrent agent benchmark

| Aspect | Status | Evidence |
| --- | --- | --- |
| Exactly-once correctness under contention | ✅ | `resilience_bench.py` — K invocations racing the same step at K = 2/5/10/25, zero violations |
| **Throughput / latency at 10, 50, 100 agents** | ❌ | Correctness is proven; *scale* is not. Distinct question: does the memory layer hold up, not just stay correct |

### 3. Memory retrieval benchmark

✅ **Done.** [`BENCHMARKS.md`](BENCHMARKS.md) — recovery read, C-SPANN vector
search, both transaction commits, end-to-end resume, real Titan embed latency,
and the same work measured on the deployed Lambda. p50/p95/p99/mean throughout,
with which path actually executed counted rather than assumed.

Vector search at scale lives in [`RESILIENCE.md`](RESILIENCE.md) — a curve
against a forced full-scan baseline, because a benchmark over 70 vectors cannot
support any claim about an ANN index.

### 4. End-to-end demo video

❌ **Not recorded.** Scripted in
[`submission/DEMO_SCRIPT.md`](../submission/DEMO_SCRIPT.md). A required
submission material, and the single largest remaining risk.

Blocked on nothing technical: Bedrock is verified, the Lambda is deployed, the
kill-and-recover flow works. It needs a recording session.

### 5. Judge-facing evidence capture

❌ **Not captured.** `assets/chaos-run/` holds the plan and shot list only.
No longer gated — the function is deployed, so the capture can show real
cold-Lambda recovery rather than a local process.

---

## P1 — high value, not load-bearing

| Item | Status | Notes |
| --- | --- | --- |
| Recovery timeline visualisation | ✅ | Built: the Gradio drill-down replays `remediation_steps`, and the interrupted step pulses with *"the process died here"* |
| AWS architecture diagram | ✅ | Two, deliberately separate: components, and the two-cold-invocation recovery sequence |
| Vector memory demo | ⚠️ | The pipeline runs and `reasoning_source` is rendered per step, but the **matched precedent and its distance are not shown** — the retrieval's *result* stays invisible |
| Benchmark dashboard | ❌ | The console shows incident KPIs, not benchmark metrics. Static charts would satisfy this |
| Transaction boundaries visible in UI | ❌ | Real, logged, durable — but not a distinct console element |
| Space first-paint / CTA | ❌ | Deliberate trade, not an oversight: `CONTINUUM_UI_LOAD_ON_OPEN=0` after a Request-Unit burn audit found the auto-refresh timer costing ~50 RU per refresh. Revisit only if cluster budget allows |
| Judge-experience dry run | ❌ | Subjective and unverifiable from repo state; needs one walkthrough with someone who has not seen the project |

---

## P2 — only if P0 is finished

Live observability, Grafana, CloudWatch dashboards, multi-agent collaboration,
stress beyond 100 agents. MCP already has a live demo (the "Ask via MCP" panel),
so that one is ✅ by accident of already being load-bearing.

---

## Explicitly not doing

- **Multi-region / regional failover.** Tempting for the "distributed" story,
  but CockroachDB Basic needs three regions to survive a region failure,
  regions **cannot be removed once added**, and the trial credits are expiring.
  A one-way door with a recurring cost, days before a deadline.
- **A third CockroachDB tool.** ADR 004: two tools done well outscores three
  done thin, and the judging criteria contain no tool-count line.

---

## Closed with evidence (was open in the superseded checklists)

Recorded so the same items don't get re-litigated:

| Item | Closed by |
| --- | --- |
| Live Bedrock path never executed | Verified end to end 2026-08-01; `embed()` returns 1024 floats, `_propose_via_bedrock()` parsed real Claude 3/3 |
| Lambda never deployed | `continuum` / eu-central-1; four cold invocations drove one incident 0 → 1 → 2 → `resolved` |
| Fresh deployment works | Clean `git clone` → `sam build` → `sam deploy` → smoke test |
| Empty database | Explicit UI empty states, plus the orchestrator's no-incident path unit-tested |
| Repeatable / multiple recoveries | Kill storm runs N back-to-back interrupt→resume cycles |
| Demo runbook matches implementation | `DEMO_SCRIPT.md` absorbed `DEMO_RUNBOOK.md`; one source of truth for the graded flow |
| Benchmarks captured | `BENCHMARKS.md`, regenerated against the live cluster and the deployed Lambda |
| Documentation drift | Repo-wide sweep: counts verified, 0 broken links, a future-dated release corrected |

---

## Standing risks

- **CockroachDB trial credits expire 2026-08-03.** Without a payment method the
  cluster is throttled from that date and the whole organisation is deleted
  after a 30-day grace period — landing mid-judging. `scripts/export_memory.py`
  snapshots the demo data as insurance; the cluster itself still needs
  resolving. See [`submission/COSTS.md`](../submission/COSTS.md).
- **Bedrock quotas are dynamic and account-level** (ADR 008). Re-probe before
  recording; a days-old green run proves nothing.
- **A green unit suite is not sufficient** for MCP or Bedrock changes — both are
  mocked at the import boundary. This has bitten twice.
