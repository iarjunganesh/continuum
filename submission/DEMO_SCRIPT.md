# Demo Video — Shooting Script (≤ 3 min)

The single source of truth for the demo: beat structure, timings, exact commands, and what to
capture. **The kill-and-recover sequence is the thing being graded — treat changes to this flow as
high-risk.**

The whole video exists to land one sentence:

> **The agent was killed mid-incident, restarted, and resumed the exact step it died on — because
> its memory lives in CockroachDB, not in the process.**

Every beat sets that up, proves it, or shows it holds at scale. Anything that does none of the three
is cut, however nice it looks.

## Hard constraints

| | |
| --- | --- |
| Runtime | **under 3:00** — hard rule, disqualifying if over. The timeline below lands ~2:52 |
| Hosting | **public** on YouTube or Vimeo — public, *not* unlisted |
| Resolution | 1920×1080, 30 fps throughout. Mixed resolutions look amateur in the first four seconds |
| Must show | the project functioning on its intended platform |
| Must show | **the CockroachDB memory layer at work** — the kill-and-resume beat |
| Must not show | third-party trademarks, unlicensed music, real infrastructure, real credentials |
| Data | synthetic only (ADR 005) — say so on screen once |
| Narration | pre-generated per beat. You never speak live — that's what makes retakes free |

---

## Why one live take and everything else stills

The kill-and-recover is the only thing here a still **cannot** prove. A screenshot of a row marked
`executing` proves nothing — the viewer has to *see* the process die and *see* the next invocation
pick that step back up, unbroken, in one shot. That beat is the video.

Everything else is a screen a judge is meant to **read**: an architecture diagram, a benchmark
chart, an `EXPLAIN` plan, a badge row. Filming those as video buys nothing and costs sharpness —
30 fps H.264 smears exactly the small text that has to stay legible.

So the shoot splits two ways:

- **Recording #1 — Kill and Recover** (OBS, one continuous take, ~50 s). Beats 6, 7, 8. Shot once,
  mined for three clips. **Do not cut between the kill and the resume** — an edit there is exactly
  where a sceptical viewer assumes the trick is.
- **Stills** — every other beat. Crisper text, free retakes, and the benchmark charts are
  *generated* rather than captured, so they can never show a number that has drifted from the
  evidence.

**What stills cost, and why it's the right trade**: a still has no cursor, so nothing in those beats
reads as "someone is operating this right now." That's fine — correct, even — for beats whose job is
*evidence*. It would be fatal for the beat whose job is *proof of life*. Which is exactly why beats
6–8 stay as one unbroken video and nothing else does. **Do not let a still creep into those three.**

**OBS settings** — Base + Output **1920×1080**, **30 fps**, cursor **visible**, clean desktop: no
notifications, no second monitor bleeding in, no personal bookmarks bar.

**Audio** — **mic OFF, desktop audio ON**. The mic is never used.

**Terminal discipline** — one full-screen terminal, large readable font (16–18 pt), high-contrast
theme, **cleared scrollback** before rolling. The structlog JSON is the star of beats 6–8; if a judge
can't read it at 1080p, the beat has failed.

---

## Step 0 — one-time prep, before recording anything

```bash
make probe-bedrock          # 1. which mode are you demoing in?
make check-drift            # 2. no stale claim can appear on screen
make migrate && make seed-data   # 3. populate the cluster
make resilience-bench       # 4. fresh evidence -> fresh charts
python scripts/build_charts.py   # 5. regenerate chart stills from that run
make run-api                # 6. orchestrator as a killable process on :8000
```

1. **`probe-bedrock`** — quotas are dynamic (ADR 008). If Bedrock is throttled, correlation and
   reasoning silently fall back and the demo *still works*, which is the danger: you'd narrate
   "Claude proposes the next step" over a deterministic replay. Confirm `reasoning_source` reads
   `bedrock` on screen. **Save the probe output into the run's `evidence/` folder whatever it says.**
2. **`check-drift`** — the README and badges are on camera in beat 13. This is what stops a stale
   number being immortalised in a video you can't edit later.
3. **`resilience-bench`** — beats 9–11 quote real figures; regenerate so charts, the committed
   evidence folder, and the screen all agree.

If every region is throttled the demo still runs end to end — correlation degrades to "no precedent"
and remediation to precedent-replay, by design. **Know which mode you're recording in before you
start**, and change the narration to match rather than narrating the live path over a fallback.

### Before rolling

- [ ] Terminal font scaled up — a judge watches this at 1080p in a small player
- [ ] Secrets off screen: `.env` closed, connection strings out of scrollback, no console tab
      showing cluster credentials
- [ ] Gradio console open and refreshed once (manual-refresh by default after the RU audit)
- [ ] `STEP_EXECUTION_SECONDS` at its default — the kill must land inside that window
- [ ] Commands **pre-typed in shell history**; recall with ↑, never type on camera
- [ ] Slack, mail, and anything that can raise a toast: closed

## Which recovery to record

1. **`--via-lambda`** — recovery as a genuine cold Lambda invocation. The strongest version of the
   claim: recovery across *invocations*, not just process restarts. The function is deployed
   (`docs/DEPLOY.md`), so **this is the one to shoot.**
2. **`--via-api` + restart** — recovery across a process restart on one machine. Still a real
   `SIGKILL`, still proves the point. Fallback only.

**Do not record option 2 and describe it as option 1.**

---

## Recording #1 — Kill and Recover (the only live take)

**One continuous take, ~50 seconds.** Two panes: left the orchestrator (structlog streaming), right
a console view of `remediation_steps` or the Gradio recovery timeline.

The sequence, unbroken:

1. Fire an alert. Left pane shows `recovered_incident_state` → `alert_embedded` →
   `correlation_query` → `remediation_proposed` → `step_checkpoint_start`.
2. **Let it sit in the execution window.** Don't rush — the pause is the tension.
3. `python scripts/chaos_kill.py --port 8000`. The left pane **dies mid-line**. No graceful
   shutdown, no goodbye. Hold on the dead terminal — silence sells it.
4. Cut to the right pane: the step sitting in **`executing`** with nothing alive to own it.
   **Hold at least 3 seconds.** This frame is the entire thesis.
5. Restart cold, fire the same alert. Left pane shows `resuming_incident` with `interrupted: true`,
   then that same `step_index` re-running and completing.

`make chaos-demo` is POSIX-only; on Windows drive it with `.\scripts\chaos_demo.ps1`.

**If the kill lands outside the execution window** the step will read `executed` rather than
`executing` and the take is dead — reshoot. Raising `STEP_EXECUTION_SECONDS` widens the window; that
is a recording aid, not a change to the guarantee.

---

## Stills — capture list

Two capture types, and the difference decides whether a still can move:

- **Type A — page capture** (no browser chrome, high resolution, pannable). Edge/Chrome:
  `Ctrl+Shift+M` → set viewport width → **DPR 2** → `Ctrl+Shift+P` → *"Capture full size
  screenshot"*. Full-page-tall PNG at twice the viewport width. Shown at 1920 it's a clean
  downscale — sharper than any recording — and the spare height is what a slow pan spends.
- **Type B — window capture** (native 1920×1080, **includes the URL bar**). `Win+Shift+S`. Only where
  a live URL must be visible. No spare pixels, so held **static**.

Save to `assets/demo-video/statics/`.

| Still | Beat | Type | What to capture | Move |
| --- | --- | --- | --- | --- |
| `s01-readme-top` | 2 | A | README from the banner through "The Problem" | pan down |
| `s02-console-idle` | 3 | A | Gradio console, incidents listed, nothing in flight | static |
| `s03-space-url` | 3 | B | The Space with its live URL in frame | static |
| `s04-timeline-executing` | 5 | A | Recovery timeline, a step mid-flight | static |
| `s05-explain-plan` | 11 | A | `EXPLAIN` showing `vector search … prefix spans` | static |
| `s06-mcp-panel` | 12 | A | Gradio "Ask via MCP" with a live answer | static |
| `s07-ci-badges` | 13 | A | README badge rows — CI green, coverage, versions | static |
| `s08-adr-list` | 13 | A | The nine-row ADR table | pan down |
| `s09-lambda-console` | 10 | B | AWS console: `continuum-orchestrator`, no provisioned concurrency | static |

**Generated stills** — do not screenshot these. They come from `scripts/build_charts.py`, so they
regenerate with the evidence and cannot drift:

| Asset | Beat | Shows |
| --- | --- | --- |
| `chart-kill-storm-{dark,light}-16x9.png` | 9 | 50 interrupted · 50 resumed · 0 duplicated · 0 lost |
| `chart-lambda-timeout-{dark,light}-16x9.png` | 10 | AWS-initiated kills, all resumed |
| `chart-vector-scale-{dark,light}-16x9.png` | 11 | C-SPANN flat vs full scan climbing |
| `chart-throughput-{dark,light}-16x9.png` | 13 | agents vs completed/s, zero failures |

---

## Motion direction — how to move a still without being annoying

The move exists to stop the frame looking frozen, **not** to be noticed. If a viewer could describe
the camera move afterwards, it was too big.

- **One move per still. Never combine** a zoom with a pan.
- **Barely perceptible**: a push-in runs **100% → ~105%** across the *entire* clip. A pan takes the
  whole beat to travel its distance.
- **Only move if you have the pixels.** A 1920-wide still in a 1920-wide frame has none, so any zoom
  is an upscale and looks softer than what it replaced. Type A captures have headroom; Type B, the
  brand cards, and the 16:9 chart/diagram PNGs are already exactly 1920×1080 and are held
  **static**. That's the correct call, not a compromise.
- **The move must be motivated.** Pan down means *keep reading*. Push in means *look at this*.
  Anything else is fidgeting.
- **Never move on beats 6–8.** They're native video; a move there is pointless and a tell that
  something was assembled.

---

## Narration script (verbatim — source of truth)

One MP3 per beat into `assets/demo-voiceover/` as `vo_NN-slug.mp3`. Per-beat files, not one long
track: it makes the timeline deterministic, and re-cutting one beat doesn't force a full re-record.

| File | Text |
| --- | --- |
| `vo_00-problem` | The conditions that cause production incidents — resource exhaustion, node failure, a bad deploy — are exactly the conditions that kill the agent responding to them. And an agent that keeps its working state in memory doesn't degrade gracefully. It stops. A human restarts the incident from zero, without knowing which actions already ran. |
| `vo_01-reveal` | Continuum is an incident-response agent whose memory lives in CockroachDB rather than in the process. Which means the process is allowed to die. |
| `vo_02-architecture` | Five agents, one write path. The orchestrator runs on Lambda with no provisioned concurrency, so every invocation starts cold. Its first action — always, before any reasoning — is a recovery read against CockroachDB. |
| `vo_03-normal` | An alert fires. Bedrock embeds it, CockroachDB's vector index finds the closest past incident, Claude proposes the next step. That step is committed as executing — before it runs. |
| `vo_04-kill` | Now watch. The process is killed mid-step. No graceful shutdown. No checkpoint call. Nothing gets a chance to clean up. |
| `vo_05-survives` | The process is gone. The step is still there — sitting in executing, with nothing alive that owns it. That row is the agent's memory, and it outlived the agent. |
| `vo_06-resume` | A cold Lambda invocation. It reads CockroachDB first, finds the interrupted step, and re-runs that exact step. Not from scratch. Not skipped. Not duplicated. |
| `vo_07-scale` | That isn't one lucky take. Fifty interrupted incidents, fifty clean resumes, zero duplicated actions, zero lost steps — counted from the durable rows, not from a log. |
| `vo_08-aws` | And it isn't only our own kill switch. Here, AWS terminates the function itself, mid-step, with no signal the process can catch. Every one of those recovered exactly once. |
| `vo_09-vector` | The memory layer scales too. As the incident corpus grows a hundredfold, CockroachDB's vector index stays flat while a full scan climbs away from it. |
| `vo_10-mcp` | The same memory is queryable live, through CockroachDB's managed MCP server — read-only, called by the application itself. |
| `vo_11-production` | Type-checked, linted, and gated in CI, with the recovery contract pinned by tests that hard-kill a real process on every push. |
| `vo_12-close` | Agents will keep dying mid-task. Continuum is the one that picks up exactly where it left off. |

---

## Final beat timeline

The cumulative column is the running total — if a beat overruns, this is where you see it before the
export does.

| # | Beat | VO | Visual | Motion | On-screen caption | Dur | Cum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Opening card | silent | `assets/demo-cards/banner-{dark,light}.svg` | **static** — exactly 1920×1080 | none | 3s | 0:03 |
| 2 | The problem | `vo_00-problem` | `s01-readme-top` | pan down | none | 16s | 0:19 |
| 3 | Reveal | `vo_01-reveal` | `s02-console-idle` → `s03-space-url` | static ×2 | `huggingface.co/spaces/iarjunganesh/continuum · live` | 10s | 0:29 |
| 4 | Architecture | `vo_02-architecture` | `architecture-diagram-{dark,light}-16x9.png` | **static** | `5 agents · 1 write path · recovery read first` | 13s | 0:42 |
| 5 | Normal operation | `vo_03-normal` | `s04-timeline-executing` | slow push-in | `Titan embed → C-SPANN search → Claude` | 13s | 0:55 |
| 6 | **The kill** | `vo_04-kill` | **#1 live** — terminal dying mid-line | native, no move | `chaos_kill.py — SIGKILL, no graceful shutdown` | 16s | 1:11 |
| 7 | **State survived** | `vo_05-survives` | **#1 live** — the row in `executing` | native, **hold 3s+** | `status: executing — and nothing is alive` | 14s | 1:25 |
| 8 | **The resume** | `vo_06-resume` | **#1 live** — cold invocation resuming that step | native, no move | `resumed: true · same step_index · executed once` | 17s | 1:42 |
| 9 | Not once — fifty times | `vo_07-scale` | `chart-kill-storm-*-16x9.png` | **static** | `50 kills · 0 duplicated · 0 lost` | 12s | 1:54 |
| 10 | AWS kills it | `vo_08-aws` | `chart-lambda-timeout-*` → `s09-lambda-console` | static ×2 | `AWS terminated the function — it still resumed` | 11s | 2:05 |
| 11 | The index earns its place | `vo_09-vector` | `chart-vector-scale-*` → `s05-explain-plan` | static ×2 | `100 → 10,000 vectors · C-SPANN stays flat` | 13s | 2:18 |
| 12 | Live query over MCP | `vo_10-mcp` | `s06-mcp-panel` | static | `Managed MCP Server · read-only` | 10s | 2:28 |
| 13 | Production | `vo_11-production` | `s07-ci-badges` → `s08-adr-list` → `chart-throughput-*` | static, pan, static | `100% coverage · 9 ADRs · CI on every push` | 14s | 2:42 |
| 14 | Close | `vo_12-close` | `assets/demo-cards/signoff-{dark,light}.svg` | **static** | `The memory outlived the failure.` | 10s | **2:52** |

---

## Assembly (Clipchamp on Win11, or CapCut)

Drop in this order. Beats 6–8 come from the **same** take — trim, don't re-cut across them.

| Track pos | Beat | Asset | Motion |
| --- | --- | --- | --- |
| 1 | 1 | `banner-{dark,light}.svg` (export 1920×1080) | static |
| 2 | 2 | `s01-readme-top` | pan down |
| 3 | 3 | `s02-console-idle` → `s03-space-url` | static ×2 |
| 4 | 4 | `architecture-diagram-{dark,light}-16x9.png` | static |
| 5 | 5 | `s04-timeline-executing` | push-in |
| 6 | **6** | **`kill-recover-take.mp4`** — the kill | native |
| 7 | **7** | **same take** — the `executing` row | native, hold |
| 8 | **8** | **same take** — the resume | native |
| 9 | 9 | `chart-kill-storm-*-16x9.png` | static |
| 10 | 10 | `chart-lambda-timeout-*` → `s09-lambda-console` | static ×2 |
| 11 | 11 | `chart-vector-scale-*` → `s05-explain-plan` | static ×2 |
| 12 | 12 | `s06-mcp-panel` | static |
| 13 | 13 | `s07-ci-badges` → `s08-adr-list` → `chart-throughput-*` | static, pan, static |
| 14 | 14 | `signoff-{dark,light}.svg` (export 1920×1080) | static |

**Transitions**: hard cuts everywhere, except a 200–300 ms cross-dissolve between the two stills
*within* beats 3, 10 and 11 — so a paired drill-down reads as navigation rather than a jump.

**Audio**: narration at a consistent level, **no music under beats 6–8**. The silence while the
terminal is dead is doing work; don't fill it.

**Captions**: burn in the on-screen captions from the timeline, and ship an `.srt` — judges may
watch muted.

---

## Honesty rules — what must not be implied on screen

These matter more than polish. A judge who catches one overstatement discounts everything else.

- **Never narrate the live Bedrock path over a fallback.** If `reasoning_source` reads
  `precedent_replay`, fix the region or change the narration. That field is on screen in beats 5 and
  8 — it will be read.
- **Never imply the numbers came from the take you just shot.** Beats 9–11 are from a committed
  evidence run carrying its own run id. Say "fifty interrupted incidents", not "we just ran fifty".
- **Never cut between the kill and the resume.** Beyond being the strongest moment, an edit there is
  exactly where a sceptic assumes the sleight of hand happened.
- **Never show anything resembling real infrastructure.** All services are fictional (ADR 005).
- **Don't claim multi-region.** Not implemented, explicitly out of scope — `docs/ROADMAP.md`.
- **Don't record option 2 and call it option 1** (see *Which recovery to record*).
- **Don't show a spend figure** you haven't checked against `submission/COSTS.md` that day.

---

## If a take goes wrong

| Symptom | Fix |
| --- | --- |
| Kill landed after the step completed | Raise `STEP_EXECUTION_SECONDS`, reshoot. The window is a recording aid |
| `reasoning_source: precedent_replay` | Bedrock throttled — `make probe-bedrock`, switch `BEDROCK_REGION`, reshoot beat 5 |
| Console blank on first paint | Expected: `CONTINUUM_UI_LOAD_ON_OPEN=0` after the RU audit. Click Refresh before capturing |
| Resume shows a *new* incident | Correlation id differed between invocations — reuse the exact same alert |
| Terminal text unreadable at 1080p | Font below ~16 pt. Increase and reshoot; this beat only works if legible |
| Lambda invocation times out on camera | Check the function's `Timeout` wasn't left low by a benchmark run — it should be 60s |

---

## Production checklist

- [ ] `make probe-bedrock` green, `reasoning_source` reads `bedrock` on screen, output saved to evidence
- [ ] `make check-drift` clean — nothing stale can appear in beat 13
- [ ] `make resilience-bench` fresh, charts regenerated from that same run
- [ ] All 9 stills captured at the right type (A vs B) into `assets/demo-video/statics/`
- [ ] Recording #1 is **one continuous take** covering beats 6–8
- [ ] Recovery recorded as **`--via-lambda`**, and narrated as such
- [ ] Exported file is **1920×1080, 30 fps, under 3:00** — check the *file*, not the timeline
- [ ] `.srt` exported alongside
- [ ] Watched start to finish, muted, in a phone-sized window — captions still legible?
- [ ] Uploaded **public** (not unlisted), link added to the README Live Demo table and
      `submission/SUBMISSION.md`

---

## Related

- `docs/ROADMAP.md` — what's evidence-backed and what's still open
- `docs/RESILIENCE.md` — the numbers quoted in beats 9–11
- `docs/BENCHMARKS.md` — latency methodology and caveats
- `assets/README.md` — evidence index and capture conventions
- `submission/SUBMISSION.md` — the rules checklist this video satisfies
