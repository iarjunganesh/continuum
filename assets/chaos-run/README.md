# Chaos Run Evidence

Captured kill-and-recover runs. One folder per run, named `<environment>-<short-id>`.

See [`../README.md`](../README.md) for the capture plan, the per-run folder layout, and the
numbered screenshot order.

## Capturing a run

    make chaos-capture

One command. `scripts/chaos_capture.py` does every step that used to be a manual checklist — probe
Bedrock and save the result, spawn a real orchestrator, fire an alert, wait for the step to be
*durably* `executing`, hard-kill the process with `scripts/chaos_kill.py`, snapshot CockroachDB at
each phase, restart cold, and verify the resume landed on the same step exactly once.

It **fails the run** rather than writing weak evidence: if the kill lands outside the execution
window, if the process survives, if the resume starts at a different step, or if any step executes
twice, the folder is marked `FAIL` and the reason recorded. A capture that passes is therefore a
capture whose claims were checked, not just narrated.

The incident is deliberately **left in the cluster** and its id printed, so the console screenshots
show the same incident the evidence JSON describes.

### Then, the screenshots

Numbered per the plan in [`../README.md`](../README.md), into `screenshots/`. Shot `03` — the
`executing` row in the CockroachDB console with no live process — is the one that carries the
argument; take it while the run is paused at step `[4/6]`, or afterwards against the incident id
the capture printed.

Every file is prefixed with the run's short id so files stay attributable if they're ever copied
out of their folder into a slide or a Devpost post.
