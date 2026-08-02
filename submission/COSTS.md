# Cost Model

What Continuum costs to run, what it has actually cost to date, and the guardrails that keep it
that way. Relevant to the **Production Readiness** criterion: a system nobody can afford to operate
isn't production-ready, and a hackathon account with no spending controls isn't either.

---

## Running cost: effectively zero

Every component sits on a free tier that is a real product tier, not a trial.

| Component | Tier | Cost | Notes |
| --- | --- | --- | --- |
| **CockroachDB Cloud** | Basic (free allowance) | $0 | The memory layer. Request Units, not instance-hours — an idle agent costs nothing |
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

## Actual spend to date: $0

As of this writing the AWS account has consumed **none** of its $120 in promotional credits, for
two compounding reasons:

1. **Nothing billable has run.** No Lambda was deployed, so there were no invocations.
2. **Bedrock never executed.** An account-level dynamic quota clamp (ADR 008 + addendum) held
   on-demand inference at effectively zero across every region and model tested. Both Bedrock paths
   degrade silently by design — correlation to "no precedent", remediation to deterministic
   precedent-replay — so the application ran end to end on fallbacks without spending anything.

The clamp was **lifted on 2026-08-01** following an AWS Support eligibility review. Bedrock spend
becomes possible from that point; the guardrails below were put in place beforehand, not after.

> **Honest note:** "$0 spent" is partly a design property and partly an accident of being
> throttled. The per-incident numbers above are modelled from published token pricing and measured
> token counts, not from an invoice. They will be reconciled against real usage once the live
> Bedrock path has run.

## Cost guardrails

Configured on the AWS account before any spend was possible, alerting to the project owner:

| Guardrail | Threshold | Behaviour |
| --- | --- | --- |
| **Monthly budget** | $100 (credits included) | Email at 50% / 80% / forecast-100%. At 100% *actual*, an IAM deny-all policy attaches to the Bedrock-invoking user — a hard stop, not a notification |
| **Credit burn tracker** | $120 (credits excluded, i.e. gross usage) | Email at 50% / 80% / 100%. Tracks how fast the promotional credits are being consumed, independent of net billing |

The deny-all action is scoped to the Bedrock-invoking IAM user only. **It does not cover a Lambda
execution role** — once the orchestrator is deployed, that role is outside the kill switch and
should be added.

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
- **One measured burn incident:** the Gradio dashboard's auto-refresh timer consumed roughly 50
  Request Units per refresh against the free allowance. It was changed to manual-refresh by
  default and the fix was verified against the live cluster. Polling UIs are the cost risk in this
  architecture, not the agent.

## Scaling estimate

At 1,000 incidents/month — well beyond a demo, plausible for a mid-size on-call rotation:

| | Volume | Cost |
| --- | --- | --- |
| Lambda | ~3,000 invocations | $0 (free tier) |
| Bedrock | ~1,000 embeddings + ~3,000 reasoning calls | ~$10–15 |
| CockroachDB | ~9,000 txns + 1,000 vector searches | likely within free allowance; Basic scales by RU |

**~$15/month at a thousand incidents.** The cost driver is Bedrock reasoning, and it scales
linearly with steps executed — which is exactly the quantity the exactly-once guarantee bounds.
