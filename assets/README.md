# Assets Index — Judge-Facing Evidence

Everything a judge needs to verify Continuum's central claim **without running the code**:

> The agent's execution environment is allowed to die mid-incident. Its memory is not.

That claim is only credible if you can see a remediation step frozen in `executing` in CockroachDB
while no process is alive to own it, and then see a cold invocation pick up *that exact step*. This
directory is where that proof lives.

> **Status — capture pending.** The directory structure and capture plan below are in place; the
> runs themselves are captured after the Lambda deploy so the evidence shows the deployed system,
> not a local-only one. Nothing here is claimed as complete until the tables list real files.

---

## Planned runs

Two runs of the **same** incident through the **same** recovery contract, in two different
execution environments — the point being that the contract holds identically because no state
lives in the process.

| Run | Folder | Environment | What it proves |
| --- | --- | --- | --- |
| **Local kill** | `chaos-run/local-<short-id>/` | `make chaos-demo` / `scripts/chaos_demo.ps1` against the live cluster | A real `SIGKILL`/`TerminateProcess` mid-step leaves `executing` durable; cold restart resumes exactly once |
| **Lambda cold** | `chaos-run/lambda-<short-id>/` | deployed `continuum-orchestrator`, no provisioned concurrency (ADR 002) | The same resume happens across *invocations*, not just across process restarts — statelessness is real, not simulated |

Each folder carries:

```
chaos-run/<id>/
├── evidence/          # raw, machine-generated — not screenshots
│   ├── <id>_incident-row.json          # incidents row at each phase
│   ├── <id>_remediation-steps.json     # the step table, incl. the frozen `executing` row
│   ├── <id>_orchestrator-log.jsonl     # structlog JSON, both invocations
│   ├── <id>_benchmark.json             # scripts/benchmark.py output for this cluster
│   └── <id>_session-metadata.json      # self-contained manifest: git SHA, cluster, region, timings
└── screenshots/       # numbered in walkthrough order
```

## Screenshot plan (numbered in walkthrough order)

| # | Shot | Why it matters |
| --- | --- | --- |
| `01` | Gradio console — incident open, steps progressing | Establishes the normal path |
| `02` | Terminal — `chaos_kill.py` firing, process gone | The kill is real, not a graceful shutdown |
| `03` | **CockroachDB console — `remediation_steps` row in `executing`, no live process** | **The money shot. This is the whole thesis.** |
| `04` | Terminal — cold restart, recovery read returning the interrupted step | Resume is driven by the DB, not by memory |
| `05` | Gradio recovery-timeline — the step replayed exactly once | Exactly-once, visible |
| `06` | CockroachDB console — final state, incident resolved atomically with last step | No orphaned/duplicated work |
| `07` | MCP Server answering a live query | ADR 003 — the tool is load-bearing, not decorative |
| `08` | Vector search returning a correlated precedent | ADR 001 — the second CockroachDB tool, working |
| `09` | CloudWatch — two separate Lambda invocations, second one cold | Lambda run only |

## Provider-side corroboration

`chaos-run/*/evidence/` is the *application's own* record of what it did. Where possible, pair it
with a screen the application cannot fake:

- **CockroachDB Cloud console** — the rows, in Cockroach Labs' own UI
- **AWS CloudWatch** — invocation records and cold-start durations, in AWS's own UI
- **CockroachDB MCP audit log** — an independent trail of what the agent actually queried

## On Bedrock and honest degradation

Both Bedrock paths in Continuum degrade **silently by design** (correlation → "no precedent",
remediation → deterministic precedent-replay), so a throttled account produces a demo that *looks*
fine while never touching Bedrock. If a captured run shows fallback behaviour, that will be stated
plainly in that run's notes with the `make probe-bedrock` output alongside it, rather than left for
a judge to discover. See ADR 008 and its addendum for the account-level quota history.

---

## Other assets

| Folder | Contents |
| --- | --- |
| [`architecture/`](architecture/) | Mermaid source + brand-themed SVG/PNG renders of the README diagram |
| [`demo-cards/`](demo-cards/) | README banner + sign-off cards (light/dark) |
| [`demo-video/`](demo-video/) | Final cut, captions, per-beat takes, and static flash-cut frames |
| `logo.svg` | Project mark, used in the README header |
