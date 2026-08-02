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
| Real `SIGKILL` mid-step | ✅ | 3/3 resumed, 0 duplicated. `test_chaos_kill_e2e.py` in CI every push; `--real-kills N` for weight |
| Injected durable interrupt (large N) | ✅ | **50/50 resumed, 0 duplicated, 0 lost, 0 wrong-step** |
| **Lambda timeout — AWS performs the kill** | ✅ | **3/3 killed by AWS, 3/3 resumed, 0 duplicated.** The function's own `Timeout` is lowered below the step window, so Lambda terminates the invocation with no catchable signal. Nobody can argue this one was staged |
| Container / execution-environment restart | ⚠️ | Largely subsumed: a Lambda timeout *is* the execution environment being taken away mid-step. A separate container harness would re-prove the same contract |
| Deployment restart mid-incident | ❌ | `sam deploy` while an incident is in flight. Lowest marginal value of the three — the same durable `executing` state is what recovery reads either way |

Metrics captured per run: resume latency (p50/p95/p99), duplicated actions, lost
steps, resumed-at-wrong-step. Correctness counts are absolute — any non-zero
value is a defect, not a percentile.

### 2. Concurrent agent benchmark

| Aspect | Status | Evidence |
| --- | --- | --- |
| Exactly-once correctness under contention | ✅ | K invocations racing the same step at K = 2/5/10/25 — **zero violations at every level** |
| Throughput / latency at 10, 50, 100 agents | ✅ | **Zero failures at every level**; 8.8 → 34.8 → 47.4 completed/s as agents go 10 → 50 → 100. Per-agent p50 rises 1132 → 1583 ms while throughput climbs — the cluster absorbs concurrency rather than rejecting it |

### 3. Memory retrieval benchmark

✅ **Done.** [`BENCHMARKS.md`](BENCHMARKS.md) — recovery read, C-SPANN vector
search, both transaction commits, end-to-end resume, real Titan embed latency,
and the same work measured on the deployed Lambda. p50/p95/p99/mean throughout,
with which path actually executed counted rather than assumed.

Vector search at scale lives in [`RESILIENCE.md`](RESILIENCE.md) — a curve
against a forced full-scan baseline, because a benchmark over 70 vectors cannot
support any claim about an ANN index.

That curve earned its keep immediately: it refused to behave, and the reason was
that `find_similar` had never used the C-SPANN index at all. Joining `incidents`
in the same statement as the `<->` ordering made CockroachDB fall back to a full
scan, so results were correct and the index was decorative. Fixed in `ebd0986`;
on a warm connection C-SPANN now holds 44 → 107 ms from 100 to 10,000 vectors
(2.4×) while the full scan grows 58 → 650 ms (11.2×) — **6.1× faster at 10,000**.
Measuring warm and cold separately is what made that visible: a ~340 ms TLS
handshake floor had been burying the whole difference.

### 4. End-to-end demo video

❌ **Not recorded** — and it remains the single largest outstanding risk, since it
is required submission material.

Everything upstream of the recording session is now done and committed:

| Input | State |
| --- | --- |
| Shooting script — beats, OBS settings, capture list, assembly, honesty rules | ✅ [`submission/DEMO_SCRIPT.md`](../submission/DEMO_SCRIPT.md) |
| Narration audio — 13 clips, 2:27.7, Amazon Polly | ✅ `assets/demo-voiceover/` (`make voiceover`) |
| Caption track, timed to the measured clips | ✅ `assets/demo-video/continuum.srt` |
| Benchmark charts, 1920×1080 PNG for the timeline | ✅ `assets/charts/` (`make charts`) |
| Opening/closing cards, architecture diagrams | ✅ `assets/demo-cards/`, `assets/architecture/` |
| **The 9 stills** | ❌ pending capture |
| **Recording #1 — kill and recover** | ❌ pending |
| **Recording #2 — live MCP query** | ❌ pending (optional; `s06` still is the fallback) |
| **Assembly, export, upload** | ❌ pending |

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
