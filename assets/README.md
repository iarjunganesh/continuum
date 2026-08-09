# Assets Index — Judge-Facing Evidence

Everything a judge needs to verify Continuum's central claim **without running the code**:

> The agent's execution environment is allowed to die mid-incident. Its memory is not.

That claim is only credible if you can see a remediation step frozen in `executing` in CockroachDB
while no process is alive to own it, and then see a cold invocation pick up *that exact step*. This
directory is where that proof lives.

> **Status — complete.** Both runs are captured *and* screenshotted (2026-08-09).
> `chaos-run/local-a2bb201d/` holds a live orchestrator hard-killed mid-step;
> `chaos-run/lambda-0b99a950/` holds the same three phases against the **deployed function with
> AWS delivering the kill**. Each carries the frozen `executing` row and the cold resume as
> machine-read JSON *and* as console frames from Cockroach Labs, Hugging Face and AWS — including
> the one shot that cannot be staged after the fact: the step sitting in `executing` with nothing
> alive to own it.

---

## The two runs

The **same** incident shape through the **same** recovery contract, in two different execution
environments — the point being that the contract holds identically because no state lives in the
process. Both are captured and screenshotted; this section describes what each one is *for*, and
the method for redoing either.

| Run | Folder | Environment | What it proves |
| --- | --- | --- | --- |
| **Local kill** ✅ | `chaos-run/local-<short-id>/` | `make chaos-capture` against the live cluster | A real `SIGKILL`/`TerminateProcess` mid-step leaves `executing` durable; cold restart resumes exactly once |
| **Lambda cold** ✅ | `chaos-run/lambda-<short-id>/` | `make chaos-capture-lambda` against the deployed `continuum-orchestrator`, no provisioned concurrency (ADR 002) | The same resume happens across *invocations*, not just across process restarts — statelessness is real, not simulated |

The Lambda run does not kill anything itself. It lowers the **function's own timeout** below its
step-execution window, so **AWS** terminates the invocation mid-step — no signal the runtime can
catch, no cleanup, no checkpoint — and the resume is a second cold invocation of the same function.
It restores the timeout unconditionally, records the `CodeSha256` of the build that produced the
evidence, and fetches the function's own CloudWatch log for the capture window: `INIT_START`, the
`REPORT … Status: timeout` where AWS does the killing, a *second* `INIT_START`, and then
`recovered_incident_state` with `last_step_status: executing`. The whole contract, in AWS's words.

`make chaos-capture` performs the kill *and* records it. That split matters: `make chaos-demo`
drives the sequence but writes nothing down, so evidence for it had to be assembled by hand
afterwards — which is how an artifact ends up disagreeing with the run that produced it. The
capture asserts its own claims (kill landed mid-window, step resumed at the same index, no step
executed twice) and marks the folder `FAIL` rather than emitting evidence for something weaker.

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

Both runs are shot against this plan, each with a `screenshots/README.md` mapping frame to claim
and stating which numbers it deliberately does **not** have as separate files — `04` lives inside
`02` (one continuous scrollback), and in the Lambda run `08` lives inside `05` (the card's full
badge row was already in frame). A number absent because it is contained in another frame is not a
missing shot, but only saying so makes that checkable.

**Every screenshot must be declared in [`../scripts/redact_evidence.py`](../scripts/redact_evidence.py)**,
with an empty region tuple if it needs no mask. `make redact-evidence --check` fails on an
undeclared file as well as an unmasked one — a raw 1920×1080 window capture carries the signed-in
user's profile photograph, and on AWS pages an account id.

**Only `chaos-run/` carries screenshots.** `resilience-run/`, `deploy-restart-run/` and the
benchmark suites are machine-evidenced by design: their results are counts and JSON, whose visual
form is the generated charts in [`charts/`](charts/) — regenerated from the evidence, so they
cannot drift the way a screenshot of a number does. Those folders deliberately have no
`screenshots/` directory rather than an empty one implying an unfinished task.

**Shot `03` must be taken during `make chaos-capture-pause`.** The frozen `executing` row exists
only inside that pause; once the run resolves, the console shows `resolved` and the state cannot be
staged again. Every other shot below can be taken afterwards against the printed incident id.

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
| `09` | CloudWatch — two separate Lambda invocations, second one cold | Lambda run only. The same facts are already captured as **text** by the harness (`<id>_cloudwatch-log.txt`); this shot is AWS's console rendering the log the harness read |

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
| [`architecture/`](architecture/) | Mermaid source + brand-themed SVG/PNG renders of the README diagrams |
| [`charts/`](charts/) | **Generated** — theme-aware benchmark charts from the newest evidence run (`make charts`). SVG for docs, PNG at 1920×1080 for the video timeline |
| [`demo-cards/`](demo-cards/) | README banner + sign-off cards (light/dark) |
| [`demo-video/`](demo-video/) | Final cut, captions, per-beat takes, and static flash-cut frames |
| [`demo-voiceover/`](demo-voiceover/) | **Generated** — Amazon Polly narration, one clip per beat (`make voiceover`) |
| [`resilience-run/`](resilience-run/) | Correctness-under-adversity evidence — kill storms, Lambda timeouts, exactly-once, vector scale |
| [`provider-evidence/`](provider-evidence/) | All four providers reporting the same facts the application reports about itself — CockroachDB Cloud (plan, region, live write traffic), Hugging Face (the running Space), Amazon Bedrock (invocation counts and per-call latency per model) and AWS Lambda (no provisioned concurrency, and a cold environment reading incident state back out of the database in CloudWatch's own log). Platform provenance, not per-run proof; see that folder's README for what each frame does and does not establish |
| [`deploy-restart-run/`](deploy-restart-run/) | The deployment-restart drill (`make deploy-restart-drill`) — a real `sam deploy` replacing the code under an open incident, and the resume that lands exactly once on the new build. Its own family, not a `resilience-run/`: it produces a single suite, and a one-suite folder dropped in there would become the newest run for `make charts` and the console panel, both of which would then find none of the suites they render |
| [`clean-clone-run/`](clean-clone-run/) | `make clean-clone-check` — the public repo cloned into a throwaway directory, a fresh venv, `pip install -r requirements.txt`, and the README's own Quick Start run inside it. Each report states what it does **not** prove (the host still supplied Python; the `.env` was copied rather than filled in by hand), because the submission checklist item it answers cannot be fully proven on a machine that already has everything installed |
| `logo.svg` | Project mark, used in the README header |

Charts and voiceover are **generated, never hand-edited** — regenerate from source rather than
touching the output, or the two copies drift. See the generated-files table in `CLAUDE.md`.
