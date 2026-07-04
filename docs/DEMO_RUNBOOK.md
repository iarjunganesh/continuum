# Demo Runbook

Target runtime: **under 3 minutes**. Every second should show either CockroachDB doing real work or the resilience beat — nothing else.

## Pre-flight (not recorded, or recorded as a fast cut)
```bash
make migrate        # apply schema.sql
make seed-data       # load incidents_seed.jsonl + embeddings
ccloud <backup/replication check>   # if ADR 004 stretch goal is built
```

## Recording Script

**0:00–0:20 — The problem, stated plainly**
On screen: the CockroachDB brief quote — *"An agent whose memory goes offline doesn't degrade gracefully, it stops."*
Voiceover: most agent demos never test this. Continuum is built specifically to test this.

**0:20–0:50 — Normal operation**
Trigger a synthetic alert (`python scripts/demo_run.py --tick`).
Show, live:
- Correlation Agent embeds the alert, queries `incident_embeddings` via CockroachDB vector search → matches a past incident
- Memory Agent writes `incidents.state = 'remediating'` + first `remediation_steps` row
- Gradio UI updates showing the matched precedent and proposed action

**0:50–1:30 — The kill**
Run `python scripts/chaos_kill.py --port 8000` (or `.\scripts\chaos_demo.ps1` for the full sequence) live on screen, timed inside a step's ~5s execution window so the step is durably stuck in `executing`.
Voiceover: the process is dead. No graceful shutdown, no checkpoint call — just gone, the way a real production failure would kill it.

**1:30–2:10 — The recovery**
Trigger the next alert-stream tick. A fresh Lambda invocation starts cold.
Show, live, in the logs or UI: the orchestrator's first action is a CockroachDB read of `incidents` + `remediation_steps` for the open correlation_id — it finds step 0 already logged, resumes at step 1, does not restart from scratch.
This is the single most important shot in the video. Do not rush it.

**2:10–2:40 — The query interface**
Via MCP Server (Claude Code or Cursor on screen), ask a live question: *"show me all open incidents and their current remediation step."* Show the real-time, correct answer.

**2:40–3:00 — Close**
Restate in one sentence: the memory outlived the failure. Link to repo + architecture doc.

## Things to Avoid
- Don't narrate setup/config — cut to the parts CockroachDB is doing
- Don't show a second, unrelated feature "for completeness" — this dilutes the one strong beat
- Don't let the kill-and-recovery segment run under 40 seconds combined — it's the whole point
