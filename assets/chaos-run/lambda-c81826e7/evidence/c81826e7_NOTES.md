# Chaos run `c81826e7` — PASS

- correlation id: `chaos-lambda-b562acaa`
- interrupted at step: **0**
- killed by **AWS**: the `continuum-orchestrator` function's timeout was lowered to `6s` (from `60s`, restored afterwards), so Lambda terminated the invocation mid-step — no catchable signal, no cleanup, no checkpoint
- resumed by a **second cold invocation of the same function**, not by a local process
- durable steps recorded runtime: `['lambda']` — read from the function's own `AWS_LAMBDA_FUNCTION_NAME`, never from config
- Bedrock at capture time: live Bedrock available
- final state: `resolved`
- steps executed: 3 · duplicated: none

## Phases

| Phase | What the database said |
| --- | --- |
| `01-before-kill` | step 0 executing; invocation in flight — statuses: `{'executing': 1}` |
| `02-frozen` | invocation terminated by AWS; interrupted step still 'executing' in CockroachDB — statuses: `{'executing': 1}` |
| `03-after-resume` | incident resolved; every step executed exactly once — statuses: `{'executed': 3}` |
