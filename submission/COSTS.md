# Cost Model

What Continuum costs to run, what it has actually cost to date, and the guardrails that keep it
that way. Relevant to the **Production Readiness** criterion: a system nobody can afford to operate
isn't production-ready, and a hackathon account with no spending controls isn't either.

---

## Running cost: effectively zero

Every component sits on a free tier that is a real product tier, not a trial.

| Component | Tier | Cost | Notes |
| --- | --- | --- | --- |
| **CockroachDB Cloud** | Basic (free allowance) | $0 | The memory layer. Request Units, not instance-hours — an idle agent costs nothing. The allowance is finite, and *this project exhausted it* on 2026-08-03 — see below |
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

**CockroachDB: the free allowance was the constraint that actually bound.** On **2026-08-03** the
cluster exhausted its 400 million Request Units and disabled itself — every connection refused with
`max connections = 0`. Nothing about the agent's steady state caused it: three `SERIALIZABLE`
transaction pairs and one vector search per incident is negligible. It was consumed by
*development* against the production cluster — resilience benchmark suites at N=50 and N=200, each
sample a full incident with real writes, plus the seeding and re-seeding those runs required, plus
the auto-refresh timer audited earlier at ~50 RU per refresh.

That is a genuine production-readiness lesson, and a cheaper one to learn here than on an on-call
rotation: **the load-testing harness is the cost risk, not the workload it measures.** A production
deployment of this design would run benchmarks against a separate cluster, so a bench run cannot
take the incident-response system offline. This one did not, and the demo went down with it — see
the first row of Known Gaps in [`SUBMISSION.md`](SUBMISSION.md).

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
- **Two measured burn incidents, neither of them the agent.** The Gradio dashboard's auto-refresh
  timer consumed roughly 50 Request Units per refresh; it was changed to manual-refresh by default
  and the fix verified against the live cluster. Then the resilience benchmark suites finished the
  allowance off on 2026-08-03. Polling UIs and load harnesses are the cost risk in this
  architecture — the incident path itself is the cheapest thing running.

## Scaling estimate

At 1,000 incidents/month — well beyond a demo, plausible for a mid-size on-call rotation:

| | Volume | Cost |
| --- | --- | --- |
| Lambda | ~3,000 invocations | $0 (free tier) |
| Bedrock | ~1,000 embeddings + ~3,000 reasoning calls | ~$10–15 |
| CockroachDB | ~9,000 txns + 1,000 vector searches | likely within free allowance; Basic scales by RU |

**~$15/month at a thousand incidents.** The cost driver is Bedrock reasoning, and it scales
linearly with steps executed — which is exactly the quantity the exactly-once guarantee bounds.
