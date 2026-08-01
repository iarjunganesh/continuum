# Demo Video — Recording Script & Production Guide

The single source of truth for the demo: the beat structure, the timings, the exact commands, and
what to capture. **The kill-and-recover sequence described here is the thing being graded — treat
changes to this flow as high-risk.**

Target runtime: **under 3 minutes**. Every second should show either CockroachDB doing real work or
the resilience beat — nothing else.

---

## Hard constraints

| | |
| --- | --- |
| Runtime | **under 3:00** — hard rule, disqualifying if over |
| Hosting | public on YouTube or Vimeo (public, not unlisted) |
| Must show | the project functioning on its intended platform |
| Must show | **the CockroachDB memory layer at work** — the kill-and-resume beat |
| Must not show | third-party trademarks, unlicensed music, real infrastructure, real credentials |
| Data | synthetic only (ADR 005) — say so on screen once |

## Pre-flight (not recorded, or recorded as a fast cut)

```bash
make probe-bedrock  # is live Bedrock open today? Quotas are dynamic (ADR 008 addendum)
make migrate        # apply schema.sql   (Windows: .\scripts\migrate_and_seed.ps1)
make seed-data      # incidents_seed.jsonl + embeddings (throttled: seed-data-offline / --from-fixture)
make benchmark      # fresh numbers, so anything on screen matches docs/BENCHMARKS.md
make run-api        # the orchestrator must run as a killable process on :8000
```

If the probe shows every region throttled, the demo still runs end to end — correlation degrades to
"no precedent" and remediation to deterministic replay/paging, by design. **Know which mode you're
recording in before you start**, and save the probe output into the run's `evidence/` folder
whatever it says.

`make chaos-demo` is POSIX-only; on Windows drive the whole sequence with `.\scripts\chaos_demo.ps1`,
which starts the API, ticks via it, kills it, and restarts — the beats below map onto that script.

### Before rolling

- [ ] `make probe-bedrock` output saved to the run's `evidence/` folder — **whatever it says**
- [ ] Terminal font scaled up; a judge watches this at 1080p in a small player
- [ ] Secrets not on screen — `.env` closed, connection strings not in scrollback, no console tab
      showing cluster credentials
- [ ] Gradio console open and already refreshed once (the dashboard is manual-refresh by default)
- [ ] `STEP_EXECUTION_SECONDS` at its default 5.0 — the kill must land inside that window

## Which recovery to record

1. **`--via-lambda`** — recovery runs as a genuine cold Lambda invocation. The strongest version of
   the claim: recovery across *invocations*, not just process restarts. Requires the deploy in
   [`docs/DEPLOY.md`](../docs/DEPLOY.md).
2. **`--via-api` + restart** — recovery across a process restart on one machine. Still a real
   `SIGKILL`; still proves the point.

Do not record option 2 and describe it as option 1.

---

## Recording script

### 0:00–0:20 — The problem, stated plainly

On screen: the CockroachDB brief quote — *"An agent whose memory goes offline doesn't degrade
gracefully, it stops."*

Voiceover: most agent demos never test this. Continuum is built specifically to test this.

Asset: `assets/demo-cards/banner-dark.png`.

### 0:20–0:50 — Normal operation

```bash
python scripts/demo_run.py --tick --via-api
```

`--via-api` is **required** — it puts the orchestrator inside the killable `:8000` process the next
beat strikes. A bare `--tick` runs in-process and finishes before you could kill it.

Show, live:

- Correlation Agent embeds the alert, queries `incident_embeddings` via CockroachDB vector search →
  matches a past incident
- Memory Agent writes `incidents.state = 'remediating'` + the first `remediation_steps` row
- Gradio console updates: the incident card appears with its step tracker; the matched precedent and
  proposed action are shown

Capture → `screenshots/01-console-incident-open.png`

### 0:50–1:30 — The kill

```bash
python scripts/chaos_kill.py --port 8000
```

Fire it live on screen, timed inside a step's ~5s execution window so the step is durably stuck in
`executing`.

Voiceover: the process is dead. No graceful shutdown, no checkpoint call — just gone, the way a real
production failure would kill it.

On screen: refresh the console — the resilience banner flips to "1 step in-flight" and the
recovery-timeline drill-down shows that step frozen in `executing`, flagged *"the process died
here."* The state outlived the process.

Capture → `02-terminal-kill.png`, and the critical one:
**`03-crdb-executing-row.png`** — the CockroachDB console showing the `remediation_steps` row in
`executing` with no live process. If you get only one good frame in the entire shoot, get this one.

### 1:30–2:10 — The recovery

```bash
python scripts/demo_run.py --tick --via-lambda          # preferred
# or: restart the API, then --tick --via-api --resume-check
```

Show, live, in the logs or UI: the orchestrator's first action is a CockroachDB read of `incidents` +
`remediation_steps` for the open correlation_id — it finds step 0 durably stuck in `executing`,
re-runs step 0 (**not skipped, not duplicated**), then commits it `executed` before advancing to
step 1. In the console's recovery timeline, the frozen step advances to `executed` and the next step
begins.

**This is the single most important shot in the video. Do not rush it.**

Capture → `04-recovery-read.png`, `05-timeline-resumed.png`

### 2:10–2:40 — The query interface

Click **"Ask via MCP"** in the Gradio UI (or `curl /api/v1/incidents/open`) — the app itself, not a
human in an IDE, calling the CockroachDB Cloud Managed MCP Server's read-only SQL tool live (ADR
003). Show the real-time, correct answer next to the same state in the incidents table above it.

Capture → `07-mcp-live-query.png`

### 2:40–3:00 — Close

Restate in one sentence: the memory outlived the failure. Link to repo + architecture doc.

Asset: `assets/demo-cards/signoff-dark.png`.

---

## Things to avoid

- Don't narrate setup/config — cut to the parts CockroachDB is doing
- Don't show a second, unrelated feature "for completeness" — it dilutes the one strong beat
- Don't let the kill-and-recovery segment run under 40 seconds combined — it's the whole point

## Voiceover

Keep the written narration in `assets/demo-video/continuum.srt` — captions and script stay one
artifact so they can't drift. Record one continuous take rather than per-beat clips; retiming a
single narration track against picture is faster than stitching ten.

Tone: plain and specific. Say "the process is dead — no graceful shutdown, no checkpoint call"
rather than "resilience is ensured."

## If a take goes wrong

| Symptom | Fix |
| --- | --- |
| Kill landed between steps, nothing stuck in `executing` | Re-run the normal-operation beat, fire the kill earlier in the window |
| Console shows nothing after the kill | Dashboard is manual-refresh by default — click refresh |
| Correlation shows "no precedent" | Bedrock is throttled *or* the seed didn't load. Check the probe output; re-seed. Don't record over it silently |
| Recovery re-runs the wrong step | Stop. That's a real bug, not a bad take — the exactly-once contract is the submission |

## Post-production checklist

- [ ] Runtime under 3:00 — verify on the exported file, not the timeline
- [ ] Watched start to finish at full length, once, before upload
- [ ] No credentials, connection strings, or account IDs in any frame — scrub frame by frame
      through terminal scrollback
- [ ] Captions exported to `assets/demo-video/continuum.srt`
- [ ] Uploaded public (not unlisted — rules require public)
- [ ] `README.md` Live Demo table updated with the real URL
- [ ] `submission/SUBMISSION.md` video items checked off
- [ ] Final cut committed to `assets/demo-video/continuum.mp4`

## Related

- Interactive walkthrough of the same flow: [`notebooks/DEMO_RUNBOOK.ipynb`](../notebooks/DEMO_RUNBOOK.ipynb)
- Evidence capture plan for the runs recorded alongside the video: [`assets/README.md`](../assets/README.md)
- Deploy the orchestrator so `--via-lambda` works: [`docs/DEPLOY.md`](../docs/DEPLOY.md)
