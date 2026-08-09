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

**Every screenshot that lands in a `screenshots/` folder must be declared in
[`../../scripts/redact_evidence.py`](../../scripts/redact_evidence.py)** — with an empty region
tuple if it genuinely needs no mask, because "declared and deliberately unmasked" is a decision and
an undeclared file is nobody having looked. `make redact-evidence --check` fails on either an
undeclared file or an unmasked declared region. That is what stops a raw 1920×1080 window capture
shipping with a real person's profile photograph, or an AWS account id, in the browser chrome.

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

Numbered per the plan in [`../README.md`](../README.md), into `screenshots/`, every file prefixed
with the run's short id — `<short-id>_NN-what-it-shows.png` — so a file stays attributable if it is
ever copied out into a slide or a Devpost post. Match the conventions the provider frames already
use: **1920×1080, unedited, URL bar in frame** for anything from a web console.

**The screenshots belong to the run they were taken during.** A folder whose evidence JSON describes
one incident and whose screenshots show another proves nothing, so an unattended run keeps its empty
`screenshots/` rather than borrowing another run's frames — the frozen state it captured is gone and
cannot be staged again. Capturing shots means starting a **new** `--pause` run and shooting that one.

Two runs are fully shot, one per environment, each with its own `screenshots/README.md` mapping
frame to claim: [`local-a2bb201d/`](local-a2bb201d/screenshots/) (a real `SIGKILL`) and
[`lambda-0b99a950/`](lambda-0b99a950/screenshots/) (AWS delivering the kill). The earlier
`local-4789422d/` and `lambda-c81826e7/` were unattended and keep their evidence JSON alone; they
are kept rather than deleted because two independent passes of the same contract is a stronger
claim than one.

#### Before you start

1. `python scripts/probe_bedrock.py` — quotas are dynamic. A run that silently fell back to
   precedent replay is honest evidence, but it is *different* evidence, and the capture records
   which mode it was in either way.
2. Open the two tabs you will need, **logged in and already on the right page**, because the pause
   window is the only time shot `03` exists and you do not want to be navigating inside it:
   - **CockroachDB Cloud console** → your cluster → **SQL Shell**
   - **The Space** — <https://huggingface.co/spaces/iarjunganesh/continuum> — click **Refresh** once
     so you know it is awake. Auto-refresh is off by design (the timer costs ~50 RU per refresh per
     open tab), so every update below is a deliberate click.
3. For the Lambda run, a third tab: **CloudWatch** → **Log groups** →
   `/aws/lambda/continuum-orchestrator`.

#### Session A — the local run

    python scripts/chaos_capture.py --pause

It prints the `correlation_id` and `incident_id`, then **holds** with the step frozen in
`executing` and no process alive to own it. Inside that window, in this order:

| Shot | Where | What to do |
| --- | --- | --- |
| `02` | Terminal | The capture's own output — the kill delivered, the process gone. Already on screen; capture it before you switch away |
| `03` | CockroachDB Cloud SQL Shell | Paste the `SELECT … FROM remediation_steps WHERE incident_id = '…'` the capture printed. **This is the money shot**: a step reading `executing` in Cockroach Labs' own UI while nothing is running |
| `01` | The Space | Click **Refresh**. The incident appears with its step in flight |

Then press **ENTER** and let it resolve. The rest of the states persist, so take your time:

| Shot | Where | What to do |
| --- | --- | --- |
| `04` | Terminal | The cold restart resuming at the same step index |
| `05` | The Space | **Refresh** → the recovery timeline, showing the step replayed exactly once and the `⟲ resumed after kill` badge |
| `06` | CockroachDB Cloud SQL Shell | Re-run the same `SELECT` → incident `resolved`, all steps `executed`, none duplicated |
| `07` | The Space | The **Ask via MCP** panel answering a live query (ADR 003) |
| `08` | The Space | A card's `⌖ recalled #N of M` with its distance and `embedding_model_id` — the vector search's result, not just its existence (ADR 001) |

#### Session B — the Lambda run

    Remove-Item Env:AWS_ACCESS_KEY_ID, Env:AWS_SECRET_ACCESS_KEY -ErrorAction SilentlyContinue
    python scripts/chaos_capture.py --via-lambda --profile continuum-admin --pause

Same sequence, with two differences worth knowing before you are inside the pause. The kill is
delivered by **AWS**, not by `chaos_kill.py`, so shot `02` is the capture reporting a function
timeout rather than a `SIGKILL`. And there is a ninth shot, which only this run can produce:

| Shot | Where | What to do |
| --- | --- | --- |
| `09` | CloudWatch → `/aws/lambda/continuum-orchestrator` | Open the log group, sort newest first. You want one frame spanning **two** log streams: the first ending `REPORT … Status: timeout`, the second opening `INIT_START` and then `recovered_incident_state` with `last_step_status: executing`. The harness already saved these lines as text in `evidence/<id>_cloudwatch-log.txt`; this is AWS's console rendering the same thing |

The calibration line matters if a run surprises you: the harness tunes the function timeout to land
inside the execution window, and an attempt that missed is discarded and retried with the rows
deleted. Only the attempt that *worked* becomes the evidence, and every attempt is listed in
`manifest.json` so the tuning is visible rather than hidden.

#### Afterwards

Drop the files into the new run's `screenshots/`, delete its `.gitkeep`, and — if the new run
supersedes an unattended one — say so in that folder rather than deleting it. Two independent
passes of the same contract is a stronger claim than one, provided nothing pretends the older run
had screenshots it never had.
