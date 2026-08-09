# Chaos Run Evidence

Captured kill-and-recover runs. One folder per run, named `<environment>-<short-id>`.

See [`../README.md`](../README.md) for the capture plan, the per-run folder layout, and the
numbered screenshot order.

## Capturing a run

    make chaos-capture          # unattended — evidence JSON only
    make chaos-capture-pause    # HOLDS at the frozen phase, for screenshots or filming
    make chaos-capture-lambda   # the DEPLOYED function, with AWS delivering the kill

`chaos-capture-lambda` is the `lambda-<id>` half. It kills nothing itself: it lowers the function's
own timeout below its step-execution window so **AWS** terminates the invocation mid-step, then
resumes with a second cold invocation of the same function. It needs an admin profile
(`lambda:UpdateFunctionConfiguration`) with `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` unset —
static keys outrank a profile in boto3's resolution order, and that misconfiguration surfaces as an
IAM `AccessDenied` rather than as a config error. It restores the original timeout unconditionally,
records the `CodeSha256` of the build under test, and saves the function's own CloudWatch log for
the window. Add `--pause` for the screenshot hold, exactly as the local capture does.

**If you intend to screenshot or film the run, use `chaos-capture-pause`.** It stops at phase
`[4/6]` — the step frozen in `executing` with no process alive to own it — and waits for ENTER,
printing the `incident_id` and the exact SQL to run. That pause is the *only* window in which the
screenshot exists: the plain target resolves the incident in the same breath, and afterwards the
console shows `resolved`. **The frozen state cannot be staged again after the fact** — this is why
run `local-4789422d` has complete evidence JSON and an empty `screenshots/` folder.

**Run the keeper capture against the Cloud cluster**, not `make local-cluster` — shot `03` is a
screenshot of the *CockroachDB Cloud console*, so a local run frames a localhost container and
evidences nothing. It costs one incident and three steps. Rehearse locally if you want the timing
first; see [`../../docs/CLUSTER_OPS.md`](../../docs/CLUSTER_OPS.md) § `chaos-capture` is split by purpose.

One command either way. `scripts/chaos_capture.py` does every step that used to be a manual checklist — probe
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
argument, and it **must** be taken during the `--pause` window. Every other shot (the resolved
incident, the step history, the Gradio timeline) can be taken afterwards against the incident id
the capture printed, because those states persist.

Every file is prefixed with the run's short id so files stay attributable if they're ever copied
out of their folder into a slide or a Devpost post.
