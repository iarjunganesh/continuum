# Demo Runbook

Target runtime: **under 3 minutes**. Every second should show either CockroachDB doing real work or the resilience beat — nothing else.

## Pre-flight (not recorded, or recorded as a fast cut)
```bash
make migrate        # apply schema.sql   (Windows: .\scripts\migrate_and_seed.ps1)
make seed-data       # load incidents_seed.jsonl + embeddings
make run-api        # the orchestrator must run as a killable process on :8000
```

`make chaos-demo` is POSIX-only; on Windows drive the whole sequence with
`.\scripts\chaos_demo.ps1`, which starts the API, ticks via it, kills it, and
restarts — the beats below map onto that script.

## Recording Script

**0:00–0:20 — The problem, stated plainly**
On screen: the CockroachDB brief quote — *"An agent whose memory goes offline doesn't degrade gracefully, it stops."*
Voiceover: most agent demos never test this. Continuum is built specifically to test this.

**0:20–0:50 — Normal operation**
Trigger a synthetic alert against the running API (`python scripts/demo_run.py --tick --via-api`) — `--via-api` is required so the orchestrator runs inside the killable :8000 process the next beat strikes; a bare `--tick` runs in-process and finishes before you could kill it.
Show, live:
- Correlation Agent embeds the alert, queries `incident_embeddings` via CockroachDB vector search → matches a past incident
- Memory Agent writes `incidents.state = 'remediating'` + first `remediation_steps` row
- Gradio console updates: the incident card appears with its step tracker; the matched precedent and proposed action are shown

**0:50–1:30 — The kill**
Run `python scripts/chaos_kill.py --port 8000` (or `.\scripts\chaos_demo.ps1` for the full sequence) live on screen, timed inside a step's ~5s execution window so the step is durably stuck in `executing`.
Voiceover: the process is dead. No graceful shutdown, no checkpoint call — just gone, the way a real production failure would kill it.
On screen: refresh the console — the resilience banner flips to "1 step in-flight" and the recovery-timeline drill-down shows that step frozen in `executing`, flagged *"the process died here."* The state outlived the process.

**1:30–2:10 — The recovery**
Trigger the next alert-stream tick. A fresh Lambda invocation starts cold.
Show, live, in the logs or UI: the orchestrator's first action is a CockroachDB read of `incidents` + `remediation_steps` for the open correlation_id — it finds step 0 already logged, resumes at step 1, does not restart from scratch. In the console's recovery timeline, the frozen step advances to `executed` and the next step begins — the same log a cold invocation replays, shown on screen.
This is the single most important shot in the video. Do not rush it.

**2:10–2:40 — The query interface**
Click "Ask via MCP" in the Gradio UI (or `curl /api/v1/incidents/open`) — the app itself, not a human in Claude Code, calling the CockroachDB Cloud Managed MCP Server's read-only SQL tool live. Show the real-time, correct answer next to the same state in the incidents table above it.

**2:40–3:00 — Close**
Restate in one sentence: the memory outlived the failure. Link to repo + architecture doc.

## Things to Avoid
- Don't narrate setup/config — cut to the parts CockroachDB is doing
- Don't show a second, unrelated feature "for completeness" — this dilutes the one strong beat
- Don't let the kill-and-recovery segment run under 40 seconds combined — it's the whole point
