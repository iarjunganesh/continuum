# ADR 008: Split the Bedrock Invocation Region from the Deployment Region

## Status
Accepted

## Context
ADR 007 assumed that deploying to eu-central-1 and using Claude Sonnet 4.5 via the EU cross-region inference profile (`eu.anthropic.claude-sonnet-4-5-20250929-v1:0`) would let Bedrock route requests across EU regions for capacity, without the app needing to track availability itself.

That assumption didn't hold. `aws service-quotas list-service-quotas --region eu-central-1 --service-code bedrock` on this account shows a hard `0` for every relevant Bedrock quota in eu-central-1 — on-demand requests/minute for Titan Text Embeddings V2, and cross-region requests/minute for every Claude Sonnet variant, including the exact reasoning model in use. `us-east-1` shows the same `0`. These quotas report `Adjustable: false`, so there's no self-service Service Quotas request path — only an AWS Support case, with no guaranteed turnaround before the Aug 18, 2026 submission deadline.

The quota is enforced at the region whose `bedrock-runtime` endpoint receives the `InvokeModel`/`Converse` call, not the region the cross-region profile ultimately executes in — so the EU cross-region profile doesn't route around a 0 quota at the calling region.

`eu-west-1` and `us-west-2` both show full default quota on this account (6000 req/min for Titan Embed V2, 10000 req/min for Claude Sonnet 4.5 cross-region).

## Decision
Add a `bedrock_region` setting (`BEDROCK_REGION`, default `eu-west-1`), used only by the two `boto3.client("bedrock-runtime", ...)` construction sites (`agents/correlation_agent.py`, `agents/remediation_agent.py`). `aws_region` (`AWS_REGION`, eu-central-1) continues to govern the Lambda's own region and stays the value CockroachDB co-location (ADR 007) cares about — this ADR does not move the Lambda or the CockroachDB cluster.

eu-west-1 was chosen over us-west-2 to stay within the EU, though this project's non-negotiable synthetic-data constraint (ADR 005) means no residency requirement actually forces that choice.

## Addendum (2026-07-08): the quota is dynamic, account-level, and model-agnostic

The Decision above chose eu-west-1 based on `aws service-quotas` listings. Live
probes have since shown those listings don't predict behaviour — the effective
quota is **dynamically adjusted** and can be 0 in a region whose paper quota is
"full default":

- **2026-07-07 probe**: eu-west-1, eu-central-1 and us-east-1 all throttle
  Titan on the first call; eu-north-1 accepts calls at a low per-minute rate.
- **2026-07-08 probe** (`scripts/probe_bedrock.py`): every probed region
  (eu-north-1, eu-west-1, eu-central-1, eu-west-3, us-west-2) throttles every
  probed model on the first call — Titan Embed V2 with "Too many requests",
  and both Claude Sonnet 4.5 *and first-party Amazon Nova Lite* with "Too many
  tokens per day". The clamp is account-level and model-agnostic; neither
  model choice nor region choice routes around it, and promotional/free-tier
  credits do not change Service Quotas (billing and quotas are separate
  systems).

Consequences of the addendum:

- The default `BEDROCK_REGION` is now **eu-north-1** (the only region ever
  observed accepting calls), aligned across `config.py`,
  `infra/template.yaml`, `.env.example`, `docs/DEPLOY.md` and `CLAUDE.md`.
- `scripts/probe_bedrock.py` (`make probe-bedrock`) is the pre-demo check:
  one InvokeModel + one Converse per candidate region, retries disabled.
- Both `bedrock-runtime` clients now set explicit botocore timeouts and
  capped retries so a throttled/hung call fails fast inside the Lambda budget
  instead of consuming it.
- The demo must not *depend* on live Bedrock: seeding uses captured Titan
  fixtures (`seed_memory.py --from-fixture`) or deterministic vectors
  (`make seed-data-offline`), and the remediation agent's deterministic
  precedent-replay fallback carries the reasoning step. Live Bedrock, when a
  probe shows a region open, is upside — not a prerequisite.
- Paths to actually lifting the clamp, in order of plausibility: an AWS
  Support case requesting an on-demand quota increase (no guaranteed
  turnaround before the deadline), sustained small successful usage to grow
  the dynamic quota (chicken-and-egg while everything throttles), or running
  the demo from an AWS account with real usage history.

## Consequences
- `AWS_REGION` and `BEDROCK_REGION` now intentionally differ — this is not the "drift" ADR 007 warned about; ADR 007's config-sync concern was about the reasoning model ID matching the deployment region's available profiles, which still holds (`eu.` prefix profile, invoked from an EU region).
- The Bedrock leg of a remediation step now carries a small cross-region hop (eu-central-1 Lambda → the `BEDROCK_REGION` endpoint, eu-north-1 per the addendum) that wasn't in ADR 007's original hot-path accounting. This doesn't affect the recovery-read race `chaos_kill.py` demonstrates, since that race is entirely between the orchestrator and CockroachDB — and correlation/reasoning are best-effort off that critical path (ADR 009) anyway.
- Before relying on any other AWS account for this project (e.g. a judge re-running it, or a fresh account for the recorded demo), re-run the quota check above — `0`-quota regions are an account-level default, not something specific to this build's original account.
- `infra/template.yaml`'s Lambda IAM policy already grants `bedrock:InvokeModel` on `Resource: '*'`, so no IAM change was needed to call a different region.
