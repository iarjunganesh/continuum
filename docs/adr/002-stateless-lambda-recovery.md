# ADR 002: Stateless Lambda, No Provisioned Concurrency

## Status
Accepted

## Context
It would be easy — and would make the demo more predictable — to run the orchestrator as a long-lived process (ECS service, or Lambda with provisioned concurrency kept warm) that holds incident state in memory and only checkpoints to CockroachDB periodically. That would still "use" CockroachDB, but it would not prove anything about memory surviving failure, because the happy path never actually loses the in-memory state.

## Decision
Run the orchestrator as a plain AWS Lambda function, invoked per alert-stream tick, with no provisioned concurrency and no assumption of a warm container. Every invocation's first action is to read incident + remediation state from CockroachDB before doing anything else.

## Consequences
- Guarantees the demo's central claim (memory survives process death) is actually true, not simulated
- Slightly higher latency per invocation (cold start + a mandatory recovery read) — acceptable for an incident-response cadence, not acceptable for a sub-100ms hot path, which is a fair limitation to state explicitly
- Makes `scripts/chaos_kill.py` a meaningful demo rather than theater — killing a Lambda invocation is realistic, not staged
