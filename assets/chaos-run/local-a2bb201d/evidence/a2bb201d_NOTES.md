# Chaos run `a2bb201d` — PASS

- correlation id: `chaos-5dd7084d`
- interrupted at step: **0**
- killed pid `38600` on port `52083` via `scripts/chaos_kill.py` (real SIGKILL/TerminateProcess, no graceful shutdown)
- Bedrock at capture time: live Bedrock available
- final state: `resolved`
- steps executed: 3 · duplicated: none

## Phases

| Phase | What the database said |
| --- | --- |
| `01-before-kill` | step 0 executing; process alive — statuses: `{'executing': 1}` |
| `02-frozen` | process dead; interrupted step still 'executing' in CockroachDB — statuses: `{'executing': 1}` |
| `03-after-resume` | incident resolved; every step executed exactly once — statuses: `{'executed': 3}` |
