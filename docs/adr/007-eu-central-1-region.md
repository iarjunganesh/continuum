# ADR 007: eu-central-1 as the Deployment Region

## Status
Accepted

## Context
The orchestrator Lambda calls CockroachDB on every invocation (the recovery read, ADR 002) and calls Amazon Bedrock twice per remediation step (embedding + reasoning). Both round trips sit on the hot path of the demo's `STEP_EXECUTION_SECONDS` window, so cross-region latency between Lambda, CockroachDB Cloud, and Bedrock is not free — it's the thing chaos_kill.py has to race against.

## Decision
Deploy to **eu-central-1** because that's where this build's CockroachDB Cloud cluster is provisioned, and use Claude Sonnet 4.5 via the **EU cross-region inference profile** (`eu.anthropic.claude-sonnet-4-5-20250929-v1:0`) rather than a direct per-region model ID, so Bedrock can route across EU regions for capacity without the app needing to track which one has availability.

## Consequences
- `AWS_REGION`, `config.py`'s default, and `infra/template.yaml`'s `BedrockReasoningModelId` must all agree — a drift between them (region set in one place, model ID assuming another) silently breaks the demo with a Bedrock access-denied error rather than a clear config error. Kept in sync across `.env.example` / `config.py` / `infra/template.yaml` as of this ADR.
- Before the recorded demo: confirm in the Bedrock console that Claude Sonnet 4.5 is enabled for the EU cross-region inference profile under this account — cross-region profile availability is account- and region-specific and can change.
- If the CockroachDB Cloud free-tier cluster is ever recreated in a different region, this ADR and the three files above need to move together.
- **Superseded in part by ADR 008**: this account's Bedrock quota probes as effectively `0` across every region and model (an account-level dynamic clamp — see ADR 008's addendum), so `bedrock-runtime` calls now target a separate `BEDROCK_REGION` (default eu-north-1) while the Lambda and CockroachDB stay here. The co-location decision above still stands for Lambda↔CockroachDB; it just never held for Bedrock in practice.
