# Cost Model

What Continuum costs to run, what it has actually cost to date, and the guardrails that keep it
that way. Relevant to the **Production Readiness** criterion: a system nobody can afford to operate
isn't production-ready, and a hackathon account with no spending controls isn't either.

---

## Running cost: effectively zero

Every component sits on a free tier that is a real product tier, not a trial.

| Component | Tier | Cost | Notes |
| --- | --- | --- | --- |
| **CockroachDB Cloud** | Basic (free trial, then free monthly allowance) | $0 | The memory layer. Request Units, not instance-hours — an idle agent costs nothing. The 30-day trial *expired* on 2026-08-03 with 99% of its credit unspent — see below |
| **AWS Lambda** | free tier (1M req/mo) | $0 | No provisioned concurrency, deliberately (ADR 002). Cold starts are the *feature* |
| **Amazon Bedrock** | on-demand, pay per token | ~$0 | Titan embeddings + Claude reasoning; usage is per-incident and tiny (see below) |
| **Hugging Face Spaces** | free CPU tier | $0 | The public Gradio demo. No card required, no sleep-on-idle billing |
| **GitHub Actions** | free for public repos | $0 | CI incl. the ephemeral CockroachDB container |
| **Codecov** | free for public repos | $0 | Coverage reporting |

**Total recurring: $0/month.**

## Per-incident marginal cost

One incident, happy path, with live Bedrock:

| Call | Model | Volume | Approx cost |
| --- | --- | --- | --- |
| Alert embedding | Titan Embed Text V2 | ~1 call, ~50 tokens | fractions of a cent |
| Next-step reasoning | Claude Sonnet 4.5 | ≤3 calls (one per step), ~400 in / ~60 out each | ~$0.01 |
| Vector search | CockroachDB C-SPANN ANN | 1 query | Request Units, within free allowance |
| Step checkpoints | 2 `SERIALIZABLE` txns per step | 6 txns | Request Units, within free allowance |

**Order of magnitude: ~1 cent per incident.** The design keeps it there deliberately — reasoning is
one call per step rather than a conversational loop, and correlation is a single round trip that
filters and ranks in one query instead of fetching candidates and re-ranking client-side.

## Actual spend to date

**AWS: still effectively $0** against $120 in promotional credits — but for a weaker reason than it
looks. Until 2026-08-01 nothing billable *could* run: no Lambda was deployed, and an account-level
dynamic quota clamp (ADR 008 + addendum) held Bedrock on-demand inference at effectively zero
across every region and model tested. Both Bedrock paths degrade silently by design — correlation
to "no precedent", remediation to deterministic precedent-replay — so the application ran end to
end on fallbacks without spending anything.

The clamp was **lifted on 2026-08-01** and both paths have run live since, locally and from the
deployed function. Spend from that point is real but small: three-digit invocation counts against
per-incident costs of about a cent.

> **Honest note:** the per-incident numbers above are modelled from published token pricing and
> measured token counts, not read off an invoice. Treat them as an order of magnitude.

**CockroachDB: the constraint that bound was a calendar, not a meter.** On **2026-08-03** the
cluster stopped accepting connections — `max connections = 0`, with an error naming a Request Unit
limit. The obvious reading was that the workload had spent the allowance. It had not. Read live
off the console before the cutoff — the screenshots that carried these figures were deleted on
2026-08-08 once they had gone stale against the live cluster, so the billing console is now the
authority and this table is the record:

| Reading | Value |
| --- | --- |
| Credits remaining | **$399 of $400** |
| Request units used | **3.42 million of 400 million** (0.86%) |
| Storage used | **19.51 MiB of 40 GiB** (0.05%) |
| Cluster created | 4 Jul 2026, 17:56 UTC |
| Trial expires | **2026-08-03** — created plus exactly 30 days |

The trial was time-boxed from the day it was created, and the console said so in advance. What
lapsed was the *entitlement*; the RU limit in the error message is the post-expiry limit, not
evidence that 400 million units were consumed. Everything this project has ever run against the
cluster — development, seeding, the chaos captures, the resilience suites at N=50 and N=200 —
came to about **one dollar**.

Two lessons, and the second one is the reason this section was rewritten:

- **Free-tier capacity has two independent limits — a meter and a clock — and only one of them is
  visible in your metrics.** Usage dashboards, budget alerts and RU guards all watch consumption.
  None of them watch an expiry date. The failure arrives looking exactly like exhaustion, because
  the error message the platform returns is about the limit that is now binding.
- **A plausible cause is not a diagnosed one.** This document previously stated that the resilience
  benchmark suites exhausted the allowance, and drew a production-readiness moral from it — *the
  load-testing harness is the cost risk, not the workload it measures*. That was inferred from the
  error text and never checked against the billing page, which was showing 0.86%. The harness
  guard added in 0.9.2 is still worth having, and the post-upgrade monthly allowance (50M RU) is
  eight times narrower than the trial's, so it now guards something real — but it was built for a
  fire that never happened.

Corrected 2026-08-06 against the console screenshots in `assets/provider-evidence/`. The demo Space
went down with the cluster either way — see the first row of Known Gaps in
[`SUBMISSION.md`](SUBMISSION.md).

### Resolution, and the standing budget

**Resolved 2026-08-06** by adding a payment method to the existing organization — the cheapest fix
available, and the one the evidence pointed at once the cause was right. Service resumed on the
same cluster with no data loss, and the org moved from a one-off trial credit onto Basic's
**recurring $15/month free allowance**.

| | Value |
| --- | --- |
| Free allowance | **50M Request Units + 10 GiB**, reset monthly |
| Measured usage, current cycle | **5.82M RU · 34.36 MiB** — 11.6% of the free RU allowance, 0.34% of storage (console reading, **2026-08-10**) |
| Resource limits set | **100M RU/mo · 10 GiB/mo** |
| Gross ceiling in console | **$25.00/mo** (100M × $0.20/M + 10 GiB × $0.50/GiB) |
| Net worst case after the credit | **≈ $10/mo** |
| Expected invoice | **$0** |

**The usage figure is dated on purpose**, and it has now absorbed the worst day this project has
had. The earlier reading of **3.42M RU** was taken on 2026-08-03 and predated the 2026-08-07 runs
against Cloud — the full resilience bench (run `e765a3c5`: 50 injected interrupts, 10 real
`SIGKILL`s, 15 Lambda timeouts, 100 exactly-once trials, a corpus grown to 10,000 vectors) and the
deploy-restart drill (`dba642ed`). The 2026-08-08 reading of **5.72M RU** included both. So the
single heaviest day of consumption in the project's life cost roughly **2.3M Request Units**,
about 4.6% of one month's free allowance, and the conclusion the old figure supported survives
contact with the data rather than merely being assumed to.

The two days since sharpen it further. Between 2026-08-08 and 2026-08-10 the project drove both
screenshotted chaos captures, a Lambda-timeout run, and the evidence queries behind them — and the
meter moved from **5.72M to 5.82M**, roughly **0.1M RU**. That is the real shape of the cost model:
a demo-shaped workload is close to free, and essentially all measurable consumption comes from
deliberately adversarial benchmarking, which is exactly what `docs/CLUSTER_OPS.md` sends to a local
cluster.

The console displays this against the **100M resource limit**, not the 50M free allowance — the
two are different numbers and it is worth knowing which one you are reading. It remains a
*reading*, not an estimate, and this file exists partly because a cluster outage was once
misdiagnosed from an error message instead of the billing page. Re-read the console before citing
it.

The cap is set at 2× the free allowance rather than exactly at it, deliberately. Reaching an RU
limit **disables the cluster** until the limit is raised or the cycle rolls over — it is a kill
switch, not an alert. A cap that trips during the judging period costs far more than $10 does, so
the ceiling is set where only a genuine runaway can reach it. At 100M, the 50%-of-limit email
fires exactly when the free tier is exceeded, which makes it a useful signal rather than noise.

The one path to a non-zero invoice is not the agent and not the benchmarks: it is the Gradio
auto-refresh timer at ~36K RU/hour per open browser tab, where a single tab left open across a
four-week judging period is ≈24M RU — about half the monthly allowance, from nobody doing
anything. It is off by default and stays off. Operating rules: [`../docs/CLUSTER_OPS.md`](../docs/CLUSTER_OPS.md).

## Cost guardrails

Configured on the AWS account before any spend was possible, alerting to the project owner:

| Guardrail | Threshold | Behaviour |
| --- | --- | --- |
| **Monthly budget** | $100 (credits included) | Email at 50% / 80% / forecast-100%. At 100% *actual*, an IAM deny-all policy attaches to the Bedrock-invoking user — a hard stop, not a notification |
| **Credit burn tracker** | $120 (credits excluded, i.e. gross usage) | Email at 50% / 80% / 100%. Tracks how fast the promotional credits are being consumed, independent of net billing |

The deny-all action is scoped to the Bedrock-invoking IAM user only. **It does not cover the Lambda
execution role**, and since the orchestrator was deployed on 2026-08-01 that role has been invoking
Bedrock outside the kill switch. Stated rather than quietly closed: the gap is small in practice —
the function is invoked manually, has no trigger, and bounds its own Bedrock calls at three per
incident via the exactly-once claim — but "the budget kill switch does not cover the thing that
actually spends" is exactly the sort of note that gets deleted instead of fixed.

### Least privilege

The credentials the application runs with are scoped to `bedrock:InvokeModel` and nothing else —
they cannot list, create, or delete AWS resources. Administrative work uses a separate profile.
This is why an accidental loop can waste tokens but cannot provision anything expensive.

## Cost characteristics worth noting

- **Idle cost is genuinely zero.** No always-on compute anywhere. Lambda bills per invocation,
  CockroachDB Basic bills per Request Unit, the Space sleeps.
- **The resilience guarantee is free.** Durability comes from committing state that was going to be
  written anyway, inside transactions that were going to happen anyway. There is no replication
  service, no checkpoint store, no sidecar.
- **The expensive failure mode is a retry storm**, not steady state — an agent that re-runs a step
  repeatedly would multiply Bedrock calls. The exactly-once forward-step claim
  (`INSERT … ON CONFLICT DO NOTHING`, ADR 009) is a correctness guarantee that doubles as a cost
  ceiling.
- **One measured burn incident, and it was not the agent.** The Gradio dashboard's auto-refresh
  timer consumed roughly 50 Request Units per refresh — ~36K RU/hour per open browser tab, which
  is most of the project's lifetime consumption. It was changed to manual-refresh by default and
  the fix verified against the live cluster. Polling UIs are the cost risk in this architecture;
  the incident path itself is the cheapest thing running, and the load harnesses turned out to
  cost about a dollar in total.

## Scaling estimate

At 1,000 incidents/month — well beyond a demo, plausible for a mid-size on-call rotation:

| | Volume | Cost |
| --- | --- | --- |
| Lambda | ~3,000 invocations | $0 (free tier) |
| Bedrock | ~1,000 embeddings + ~3,000 reasoning calls | ~$10–15 |
| CockroachDB | ~9,000 txns + 1,000 vector searches | likely within free allowance; Basic scales by RU |

**~$15/month at a thousand incidents.** The cost driver is Bedrock reasoning, and it scales
linearly with steps executed — which is exactly the quantity the exactly-once guarantee bounds.
