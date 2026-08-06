# Demo Video — Shooting Script (≤ 3 min)

> **Target 2:50–2:55** (hard cap **3:00**, disqualifying if over) · **public** on YouTube · 1920×1080 / 30 fps ·
> no copyrighted music · synthetic data only (ADR 005).
> **Status: not yet shot.** Ready and committed: narration (13 clips), captions, charts, cards,
> both diagrams, and `s03` under `assets/provider-evidence/`. Outstanding: **8 stills, Recording #1
> (the take that matters), Recording #2 (optional), Session C (evidence capture — not filmed), and
> the cut.** Nothing here is blocked on anything — see the time budget below.

**Time budget — this is a one-day shoot, and the deadline is the only hard constraint.** Everything
below is written to make each beat correct on the first attempt, not to be worked through in order
on the day. Plan roughly: OBS + desktop setup **30 min** · Step 0 prep **20 min** · Recording #1
**45 min** including retakes · Session C evidence capture **15 min** · stills **45 min** ·
assembly and export **90 min**. That is one
focused day with slack, and it fits several times over in the time remaining — but only if it
starts. **If you are running long, cut in this order**: Recording #2 (beat 12 falls back to the
`s06` still, explicitly sanctioned below) → the `s09` Lambda console still (beat 10 runs on the
chart alone) → beat 13's third still. **Never cut, shorten, or re-shoot-in-pieces beats 6–8.**
A rough cut of beats 6–8 with everything else missing is a submittable video; a polished everything
else without beats 6–8 is not.

The whole video exists to land one sentence:

> **The agent was killed mid-incident, restarted, and resumed the exact step it died on — because
> its memory lives in CockroachDB, not in the process.**

Every beat sets that up, proves it, or shows it holds at scale. Anything that does none of the three
is cut, however good it looks.

**Every judging criterion is earned on screen** — the mapping, so nothing is left to the judge's
inference:

| Criterion | Where it's earned |
| --- | --- |
| **Agentic Memory Design** | Beats 4, 7, 8 — recovery-read-first control flow, the `executing` row outliving its process, the cold resume |
| **Technical Implementation** | Beats 5, 11, 12 — Titan embed → C-SPANN search → Claude, the `EXPLAIN` plan, the live MCP query |
| **Real-World Impact** | Beats 2, 10 — the incident-response problem stated plainly; AWS itself terminating the function |
| **Production Readiness** | Beats 9, 13 — 50-kill evidence run, CI badges, ADR table, throughput at zero failures |
| **Creativity & Originality** | Beats 6–8 — killing your own demo on camera is the idea, and almost nobody does it |

---

## Why one live take and everything else stills

The kill-and-recover is the only thing here a still **cannot** prove. A screenshot of a row marked
`executing` proves nothing — the viewer has to *see* the process die and *see* the next invocation
pick that step back up, unbroken, in one shot. That beat is the video.

Everything else is a screen a judge is meant to **read**: an architecture diagram, a benchmark
chart, an `EXPLAIN` plan, a badge row. Filming those as video buys nothing and costs sharpness —
30 fps H.264 smears exactly the small text that has to stay legible.

So the shoot splits three ways:

- **Recording #1 — Kill and Recover** (OBS, **one continuous take**, ~50 s). Beats 6, 7, 8. Shot
  once, mined for three clips. **Do not cut between the kill and the resume** — an edit there is
  exactly where a sceptical viewer assumes the trick is.
- **Recording #2 — Live MCP query** (OBS, ~15 s). Beat 12. Short, free, retake as often as you like.
  It's video for the same reason beat 9 was in the reference build: "queryable *live*" is a claim
  about something happening now, and a still of an answer can't distinguish a live query from a
  hardcoded string.
- **Stills** — every other beat. Crisper text, free retakes, and the charts are *generated* rather
  than captured, so they can never show a number that has drifted from the evidence.

There is also a fourth thing to capture on shoot day that is **not part of the video at all**:

- **Session C — Evidence capture** (`make chaos-capture-pause`, ~5 min). Produces the judge-facing
  `assets/chaos-run/` folder and its console screenshots. Nothing from it appears on the timeline.
  Do it in the same sitting because the browser tabs and cluster state are already staged — but see
  *Session C* below for why it **cannot** double as Recording #1.

**What stills cost, and why it's the right trade**: a still has no cursor, so nothing in those beats
reads as "someone is operating this right now." That's fine — correct, even — for beats whose job is
*evidence*. It would be fatal for the beat whose job is *proof of life*. Which is exactly why beats
6–8 stay as one unbroken video and nothing else does. **Do not let a still creep into those three.**

---

## OBS — set this up once, before either recording

Every setting below is chosen; none is a default. Get these right once and both takes are usable.

**Settings → Output** — set *Output Mode* to **Advanced** first, or half of these aren't visible.

| Where | Setting | Value | Why |
| --- | --- | --- | --- |
| Output → Recording | Type | **Standard** | |
| Output → Recording | Recording Path | a folder you'll find again — not Desktop | |
| Output → Recording | Recording Format | **MKV** | A crash or a hard-kill of the *wrong* window leaves an MKV playable and an MP4 corrupt. Remux after (below) |
| Output → Recording | Video Encoder | hardware (NVENC / QuickSync / AMF) if offered, else x264 | Hardware keeps the capture from stealing CPU from the thing you're filming |
| Output → Recording | Rate Control | **CBR** | |
| Output → Recording | Bitrate | **12000–16000 Kbps** | Terminal text on a dark background is where low bitrate shows first |
| Output → Recording | Keyframe Interval | 2 s | |
| Output → Audio | Track 1 | enabled | |

**Settings → Video**

| Setting | Value |
| --- | --- |
| Base (Canvas) Resolution | **1920×1080** |
| Output (Scaled) Resolution | **1920×1080** — must match Base; any scaling softens text |
| Downscale Filter | Bicubic (irrelevant if the two match, set it anyway) |
| Common FPS Value | **30** |

**Settings → Audio — set once and never touch again**

- **Mic/Auxiliary Audio: Disabled.** Not muted in the mixer — *Disabled* in Settings → Audio, so a
  stray click in the mixer can't re-arm it. **You never speak during either take.** Narration is
  pre-generated in `assets/demo-voiceover/`.
- **Desktop Audio: Default (ON).** Nothing in this shoot plays sound, so this is precautionary — but
  you can only mute audio you actually captured, and discovering afterwards that a take is silent
  when you needed it is unrecoverable.
- **Do not vary this per take.** A per-take toggle is exactly how the one take you can't cheaply
  redo comes back wrong.

**Settings → Hotkeys**

- Set **Start Recording** and **Stop Recording** to a key you won't hit by accident (`Ctrl+Shift+F9`
  / `Ctrl+Shift+F10`). **This is not optional**: without it you have to click OBS's own window to
  start, which means OBS is on screen in the first and last seconds of every take.

**Sources** — one **Display Capture** source. Not Window Capture: the kill takes the window away
mid-take, and a Window Capture source follows it into oblivion, leaving you with a black frame at
the exact moment the beat needs the dead terminal visible.

- Right-click the source → **Properties** → tick **Capture Cursor**. The cursor is wanted here; it's
  what makes beats 6–8 read as someone operating a machine.

**After each take**: File → **Remux Recordings** → pick the MKV → Remux. Rename the MP4 to the name
this script gives it. Editors handle MP4 predictably and MKV variably.

### Desktop hygiene — do this before the first take, not between takes

- [ ] **Windows Focus Assist → Do Not Disturb.** One Teams toast in the middle of the kill beat
      costs you the whole take.
- [ ] Close Slack, mail, Discord, Steam, and anything with a badge that can update.
- [ ] Single monitor, or at minimum make sure the captured display has nothing personal on it.
- [ ] Browser: a clean profile or a new window — **bookmarks bar hidden** (`Ctrl+Shift+B`), no
      extension icons you can't explain, **and every tab closed except the ones being filmed**. A
      row of unrelated tabs is the single most common thing that makes a demo look unrehearsed.
- [ ] Desktop wallpaper: neutral. It will be visible for a moment somewhere.
- [ ] Terminal: **one full-screen window**, font **16–18 pt**, high-contrast theme, **scrollback
      cleared** (`Clear-Host`). The structlog JSON is the star of beats 6–8; if a judge can't read it
      at 1080p in a small player, the beat has failed.
- [ ] Secrets off screen: `.env` closed, connection strings out of scrollback, no cluster console
      tab showing credentials.
- [ ] Commands **pre-typed into shell history** so you recall them with ↑ and never type on camera.

**Mouse discipline** — move **deliberately**, click **confidently**, **pause** on anything a judge is
meant to read. No rapid scrolling, no hovering, no idle cursor circling, no tab-switching mid-beat.
This is most of what separates footage that reads as polished from footage that reads as a rehearsal.

---

## Step 0 — one-time prep, before recording anything

Run this whole block and read the output. It regenerates every generated asset from current
evidence, so nothing on screen can be stale:

> **`make` is not installed on the shoot machine** — not in PowerShell, not in Git Bash. The
> `Makefile` remains the source of truth for *what* each step is; the commands below are what you
> actually type. Every runnable block in this document is PowerShell-native for that reason. If you
> would rather have the targets, `winget install ezwinports.make` — but do that days ahead, not on
> shoot day, and re-open the shell so `PATH` picks it up.

| Makefile target | What to type on Windows |
| --- | --- |
| `make probe-bedrock` | `python scripts/probe_bedrock.py` |
| `make check-drift` | `python scripts/check_drift.py` |
| `make migrate` + `make seed-data` | `.\scripts\migrate_and_seed.ps1` (add `-Offline` for zero-AWS vectors) |
| `make voiceover` | `python scripts/generate_demo_voiceover.py` |
| `make chaos-capture-pause` | `python scripts/chaos_capture.py --pause` |
| `make charts` | `python scripts/build_charts.py` |
| `make obs-assets` | `python scripts/build_obs_assets.py` |
| `make run-api` | `python -m uvicorn api.main:app --port 8000` |
| `make coverage` | `pytest tests/unit --cov=agents --cov=api --cov=observability --cov-report=term` |

```powershell
cd C:\ws\continuum

python scripts/probe_bedrock.py     # 1. which mode are you demoing in?
python scripts/check_drift.py       # 2. no stale claim can appear on screen
.\scripts\migrate_and_seed.ps1      # 3. populate the DEMO cluster (see the warning below)
python scripts/generate_demo_voiceover.py   # 4. narration + captions (only if wording changed)
```

1. **`probe-bedrock`** — quotas are dynamic (ADR 008). If Bedrock is throttled, correlation and
   reasoning silently fall back and the demo *still works*, which is the danger: you'd narrate
   "Claude proposes the next step" over a deterministic replay. Confirm `reasoning_source` reads
   `bedrock` on screen. **Save the probe output into the run's `evidence/` folder whatever it says.**
2. **`check-drift`** — the README and badges are on camera in beat 13. This is what stops a stale
   number being immortalised in a video you can't edit later.
3. **`migrate` + `seed-data`** — these two, and *only* these two, run against the Cloud demo cluster
   in `$COCKROACH_DATABASE_URL`. That is the cluster the Space and the deployed Lambda share and the
   one judges open, so nothing else in this shoot points at it.

> **Do NOT run `make resilience-bench` on shoot day.** It refuses to run against a
> `*.cockroachlabs.cloud` DSN without `--allow-cloud-burn` ([`scripts/resilience_bench.py`](../scripts/resilience_bench.py)),
> so the command aborts mid-prep — and overriding the guard is worse: an N=200 run once left 665
> incidents, 431 frozen in `remediating`, on the cluster judges open. The charts for beats 9–11 are
> **already generated and committed** from evidence run `1f98a6fc`; they cannot drift, because
> `make charts` derives them from that folder. Regenerating buys nothing and risks the demo surface.
> If you genuinely need fresh numbers, do it days ahead against `make local-cluster`, per
> [`docs/CLUSTER_OPS.md`](../docs/CLUSTER_OPS.md), then re-run `make charts` and commit.

If every region is throttled the demo still runs end to end — correlation degrades to "no precedent"
and remediation to precedent-replay, by design. **Know which mode you're recording in before you
start**, and change the narration to match rather than narrating the live path over a fallback.

**Pick one theme — dark or light — and hold it** across the UI, the cards, the diagrams and the
charts. Every generated asset ships in both variants; mixing them mid-video reads as an accident.

## Which recovery to record

**You cannot film a Lambda being killed.** `chaos_kill.py` kills a local process by PID or port; a
deployed function has neither from your terminal. So the take is a **hybrid**, and it is the
strongest *honest* version of the claim:

| Beat | Command | Why this one |
| --- | --- | --- |
| 6–7 — the kill | `--via-api`, then `chaos_kill.py --port 8000` | A genuine `SIGKILL` against a process you can see die on camera. This half **must** be local |
| 8 — the resume | `--via-lambda` | The resume is a **real cold invocation of the deployed function**, which is exactly what `vo_06-resume` narrates |

This works because the local API and the deployed Lambda **read the same cluster** — the function's
`COCKROACH_DATABASE_URL` is the same DSN your `.env` uses ([`infra/template.yaml`](../infra/template.yaml)).
The killed local process leaves the step durably `executing`; the Lambda, in another account-region
entirely, picks up *that* row. The handoff crossing an execution-environment boundary is a stronger
demonstration than a same-machine restart, not a weaker one.

**Fallback if the Lambda misbehaves on camera** (throttle, cold-start stall, expired credentials):
resume with `--via-api` after restarting the API locally. Still a real kill, still a real cold resume from
CockroachDB. **If you do that, change the beat-8 narration** — `vo_06-resume` says *"A cold Lambda
invocation"*, and that sentence would no longer be true. Re-record that one clip via `make voiceover`
rather than letting it play over the wrong footage.

---

## Recording #1 — Kill and Recover (the take that matters)

**One continuous take, ~50 seconds. Shoot this first, by itself, when you're fresh.**

### OBS state for this take — verify every line before you roll

| | |
| --- | --- |
| Scene | the Display Capture scene from the setup section |
| Source | **Display Capture**, Capture Cursor **on** — *not* Window Capture. The kill destroys the window, and a Window Capture source follows it into a black frame at the exact moment the beat needs the dead terminal visible |
| Base / Output | 1920×1080 / 1920×1080, 30 fps |
| Format / bitrate | MKV, CBR 12–16 Mbps |
| **Mic / Aux** | **Disabled** (Settings → Audio, not muted in the mixer) — you never speak |
| **Desktop Audio** | **ON**. Nothing plays in this take; it stays on so audio state never varies between takes |
| Start / Stop | **hotkey only** (`Ctrl+Shift+F9` / `F10`). Clicking OBS puts OBS in frame |
| Preview | check the OBS preview shows **both panes fully**, no cropping, before rolling |
| Disk | ≥ 2 GB free — at 16 Mbps a 50 s take is ~100 MB, but a retake session eats it fast |

**Last check before the hotkey**: Focus Assist on, scrollback cleared, terminal ≥ 16 pt, no `.env`
or connection string anywhere in either pane.

### The take

Two panes, side by side and both readable at 1080p: **left** the orchestrator (structlog streaming),
**right** a console view of `remediation_steps` or the Gradio recovery timeline.

Set the panes up, then start the API and let it settle *before* you start recording:

```powershell
# Pane 1 — the orchestrator, as a killable process
cd C:\ws\continuum
Clear-Host
python -m uvicorn api.main:app --port 8000
```

Then, in pane 2, with OBS rolling (hotkey — do not click OBS):

```powershell
# 1. Fire an alert. Watch the left pane reach step_checkpoint_start.
python scripts/demo_run.py --tick --via-api

# 2. LET IT SIT. Do not rush this — the pause is the tension.

# 3. The kill. Left pane dies mid-line: no graceful shutdown, no goodbye.
python scripts/chaos_kill.py --port 8000

# 4. Show the durable state. HOLD AT LEAST 3 SECONDS on this frame —
#    the step sitting in `executing` with nothing alive to own it is the whole thesis.

# 5. THE RESUME — a cold invocation of the DEPLOYED function. Nothing local is
#    restarted: the left pane stays dead on screen while the right pane shows the
#    deployed Lambda picking up the same step_index. `resumed: true`,
#    `reexecuted_after_interrupt: true`, then that step completing.
python scripts/demo_run.py --tick --via-lambda --resume-check
```

**Leave the dead terminal in frame during step 5.** The killed process visibly still gone while
something *else* completes its step is the whole thesis in one frame — restarting the local API
would throw that away. (Fallback only, if the Lambda stalls: `python -m uvicorn api.main:app --port 8000` then
`python scripts/demo_run.py --tick --via-api --resume-check`, and re-record `vo_06-resume` — see
*Which recovery to record*.)

Before rolling, confirm the Lambda leg works at all — you do not want to discover an expired
credential mid-take:

```powershell
# unset the Bedrock-only static keys first, or boto3 ignores the profile (see CLAUDE.md)
python scripts/demo_run.py --tick --via-lambda --new   # throwaway incident, not the demo one
```

Windows shortcut for the local-only sequence: `.\scripts\chaos_demo.ps1` (`make chaos-demo` is
POSIX-only). It resumes via the API, not the Lambda — useful for rehearsing the timing of the kill,
not for the final take. Drive the sequence above by hand the first time so you know what each frame
should look like.

### Stopping and saving

1. **Stop with the hotkey**, not by clicking OBS.
2. Wait ~2 s before touching anything — OBS finalises the file after the stop.
3. File → **Remux Recordings** → select the MKV → **Remux**.
4. Rename the resulting MP4 to **`kill-recover-take.mp4`**, in `assets/demo-video/`.
5. Verify what you actually captured before you trust it:

```powershell
ffprobe -v error -show_entries format=duration `
  -show_entries stream=codec_name,width,height,r_frame_rate `
  -of default=nw=1 assets\demo-video\kill-recover-take.mp4
```

Expect `1920`, `1080`, `30/1`, `h264`, and a duration around 50 s. A width of 2560 or an fps of 60
means OBS was capturing at your monitor's native settings, not the ones above — fix and reshoot now,
while the cluster state is still fresh.

**Then check the content**: the interrupted step must read **`executing`**, not `executed`. If the
kill landed after the step completed, the take is dead — reshoot. Raising `STEP_EXECUTION_SECONDS`
widens the window; that is a recording aid, not a change to the guarantee.

---

## Recording #2 — Live MCP query (OBS, ~15 s)

Free and retakeable. Skip it only if you'd rather run beat 12 as the `s06` still.

### OBS state for this take

**Identical to Recording #1 — change nothing.** That is the point of setting it once: the two takes
land on the same timeline, and a resolution or fps difference between them is visible as a quality
shift at the cut. Specifically, still true here:

| | |
| --- | --- |
| Source | **Display Capture**, Capture Cursor **on** |
| Base / Output | 1920×1080 / 1920×1080, 30 fps |
| **Mic / Aux** | **Disabled** |
| **Desktop Audio** | **ON** — unchanged from take #1, even though nothing plays |
| Start / Stop | **hotkey only** |

The one thing to re-check: the browser window is at the **same size and page zoom** as any Gradio
still you captured, or beat 12 will jump against beats 3 and 5.

### The take — beat 12

1. Gradio console open, **"Ask via MCP"** panel visible, previous answer cleared.
2. Start OBS (hotkey).
3. Type a short question — pre-decide the wording, don't compose on camera — and submit.
4. Let the answer render fully. **Pause on it** for 2–3 seconds; that pause is the beat.
5. Stop with the hotkey, wait ~2 s, remux, save as **`mcp-query-take.mp4`**.
6. `ffprobe` it exactly as above — same 1920×1080 / 30 fps expectation.

---

## Session C — Evidence capture (not filmed, but do it the same day)

`make chaos-capture-pause` produces the judge-facing artifact the *repo* needs: a
`assets/chaos-run/local-<id>/` folder holding a provenance manifest, the three phase snapshots read
straight out of CockroachDB, the orchestrator's own structlog, the Bedrock probe — and the console
screenshots that go with them. **None of it lands on the video timeline.** It is what a judge opens
when they want to verify the claim without watching anything.

### Why this cannot be Recording #1

Tempting, because it stages the same moment and pauses exactly where the camera wants to linger.
But `chaos_capture.py` resumes with a **second local uvicorn process**
([`scripts/chaos_capture.py`](../scripts/chaos_capture.py) — `srv2 = Orchestrator(...)`), not a
Lambda invocation. Beat 8's committed narration says *"A cold Lambda invocation."* Filming this run
would put that sentence over a local process restart, which is precisely the substitution the
Honesty rules forbid.

| | Recording #1 | Session C |
| --- | --- | --- |
| Purpose | the video's beats 6–8 | the repo's evidence folder |
| Resume performed by | **cold Lambda** (`--via-lambda`) | second local process |
| Produces evidence JSON | no | **yes**, with a manifest |
| Frozen state held by | you, between typed commands | `--pause`, until ENTER |

Both are real kills and both prove the contract. They differ in *who resumes* and *what is written
down*, and each is the right tool for its job. Run them as two sessions, back to back.

### Steps

Run this against the **Cloud** cluster — shot `03` is a screenshot of the CockroachDB *Cloud*
console, so a local run frames a container and evidences nothing
([`docs/CLUSTER_OPS.md`](../docs/CLUSTER_OPS.md) § `chaos-capture` is split by purpose). It costs
one incident and three steps.

Have open before you start: the **CockroachDB console SQL shell**, and the **Gradio console**
(click Refresh once — it is blank on first paint by design).

```powershell
python scripts/chaos_capture.py --pause
```

It probes Bedrock, spawns a real orchestrator, fires an alert, waits for the step to be *durably*
`executing`, hard-kills the process — then **stops** and prints the `incident_id` and the SQL to
run. Nothing is running during the pause; take as long as you like.

While paused, capture into `assets/chaos-run/local-<id>/screenshots/`, prefixed with the run id:

| Shot | What | Why it can only happen now |
| --- | --- | --- |
| `03` | CockroachDB console — the `remediation_steps` row in `executing` | **The money shot.** Once you press ENTER the incident resolves and the console shows `resolved`. It cannot be staged again |
| `01` | Gradio console — the incident open, step mid-flight | Same window; cheaper to take now than to re-stage |

Press **ENTER**. The run resumes, resolves, verifies exactly-once from the durable rows, and writes
the folder. Shots `02`, `04` and `05` (terminal scrollback, the resolved timeline) can be taken
afterwards at leisure — those states persist.

**If the capture prints `FAIL`**, keep the folder. A failed capture is a fact about the system, not
a mistake to hide — the script marks it and records why, and that is the behaviour that makes a
passing folder worth trusting.

### Afterwards

The new run supersedes `local-4789422d`, which has complete evidence JSON and an empty
`screenshots/` folder because it was captured before `--pause` existed and its incident has long
since resolved. Update `assets/README.md`, `assets/chaos-run/README.md` and the Known Gaps row in
[`SUBMISSION.md`](SUBMISSION.md) to point at the new id.

---

## Stills — capture list

**OBS is not involved here.** Close it, or at least make sure it isn't recording — a still captured
while OBS is running is identical, but a forgotten recording eats disk and confuses which take is
which later. Stills come from the browser's own capture and `Win+Shift+S`.

Two capture types, and the difference decides whether a still can move:

- **Type A — page capture** (no browser chrome, high resolution, pannable). Edge/Chrome:
  `Ctrl+Shift+M` for the device toolbar → set a **viewport width** (see below) → **DPR 2** →
  `Ctrl+Shift+P` → *"Capture full size screenshot"*. Full-page-tall PNG at twice the viewport width.
  Shown at 1920 it's a clean downscale — sharper than any recording — and the spare height is what a
  slow pan spends.
- **Type B — window capture** (native 1920×1080, **includes the URL bar**). `Win+Shift+S`. Only where
  a live URL must be visible. No spare pixels, so held **static**.

**Viewport width is the setting that decides whether the beat looks composed or empty.** GitHub
renders a README into a centred column ~800 px wide, so captured at a 1920 px viewport it fills under
half the frame and reads as a strip of text floating in whitespace. Capture **GitHub pages at a
1200–1280 px viewport**: the column then fills the frame, and at DPR 2 you still get a 2400–2560 px
PNG, comfortably above the 1920 you need. Capture the **app's own pages at 1920** — they're
full-bleed. Don't also change page zoom; viewport width alone does it, and stacking both makes the
result hard to predict.

Save everything to `assets/demo-video/statics/`.

**Some of these are already captured** — see *Already captured: provider evidence* below before
shooting anything. `s03` is done; `s09` is one screenshot away.

| Still | Beat | Type | Viewport | What to capture | Move |
| --- | --- | --- | --- | --- | --- |
| `s01-readme-top` | 2 | A | 1280 | README from the banner through "The Problem" | pan down |
| `s02-console-idle` | 3 | A | 1920 | Gradio console, incidents listed, nothing in flight | static |
| ~~`s03-space-url`~~ ✅ | 3 | B | — | **Already captured** — use `assets/provider-evidence/1080p/01.space-console-executing-banner.png` (1920×1080, live URL in frame) | static |
| `s04-timeline-executing` | 5 | A | 1920 | Recovery timeline, a step mid-flight, `correlation_source: bedrock` visible | slow push-in |
| `s05-explain-plan` | 11 | A | 1280 | `EXPLAIN` showing `vector search … prefix spans` | static |
| `s06-mcp-panel` | 12 | A | 1920 | Gradio "Ask via MCP" with a live answer — **fallback if Recording #2 is skipped** | static |
| `s07-ci-badges` | 13 | A | 1280 | README badge rows — CI green, coverage, versions | static |
| `s08-adr-list` | 13 | A | 1280 | The nine-row ADR table | pan down |
| `s09-lambda-console` | 10 | B | — | AWS console: `continuum-orchestrator`, no provisioned concurrency. **Capture steps: `assets/provider-evidence/README.md` shot `12`** | static |

### Already captured: provider evidence

`assets/provider-evidence/` holds console captures taken from **Cockroach Labs' and Hugging Face's
own UIs** — screens this project cannot fake. They were captured as repo evidence first, so most
have no beat and belong in the README and on Devpost rather than in a 3-minute video. Three of them
do earn screen time, and one closes a still outright.

`make obs-assets` renders the OBS-ready set into `assets/provider-evidence/1080p/`. **Use that
folder on the timeline, not the parent** — everything in it is exactly 1920×1080, and nothing in it
was downscaled: short captures are padded, and anything taller than a frame became a pan video
instead of a shrunken still.

| Asset (`1080p/`) | Use | Why it earns the time |
| --- | --- | --- |
| `01.space-console-executing-banner.png` | **Beat 3** — replaces `s03-space-url` | The live Space URL and a step sitting in `executing`, in one 1080p frame. Nothing to shoot |
| `03.crdb-cluster-overview-eu-central-1.png` | **Beat 13**, after `s07-ci-badges` | `Plan Basic · Cloud AWS · Region Frankfurt (eu-central-1) PRIMARY`, in Cockroach Labs' own UI. The "CockroachDB deployed on AWS" requirement, corroborated by a screen we don't control. Hold static, it's exactly 1920×1080 |
| `06.crdb-sql-activity-fingerprints.png` | **Beat 13** alternative | Real statement fingerprints — `INSERT INTO incidents`, `remediation_steps`, `incident_embeddings` with execution counts. The single write path visible as actual traffic |
| `00.space-console-full-page.pan.mp4` | **Beat 3** alternative to `s02-console-idle` | A 24.8 s pan down the whole console at native scale. Trim to the 16 s the beat has; it moves, so it can replace a static still if beat 3 feels flat. **Note it shows a step in flight**, so it reads as beat 3 *or* beat 5, not as "idle" |
| `05.crdb-metrics-full-page.pan.mp4` | optional B-roll | 7 s pan over the Metrics dashboard. No beat needs it — use only if a gap opens in the cut |
| `02`, `04`, `07`, `08` | **not in the video** | Trial state, month-scale traffic, job history, the MCP service account. Repo and Devpost evidence; none of them advances the one sentence this video exists to land |

**The Bedrock and Lambda console captures are still to take**, and they matter more than the ones
above: `assets/provider-evidence/README.md` has exact click-paths as shots `09`–`14`. Shot `12`
*is* `s09-lambda-console` for beat 10. Shot `10` — CloudWatch `AWS/Bedrock` invocation counts per
model — has no beat but is the only artifact that proves, from AWS's side, that the live Bedrock
path ran rather than the silent fallback; capture it right after a run, because the graph is
time-windowed.

**Do not put any of these inside beats 6–8.** They are stills and pans of pages, and those three
beats are one continuous take for a reason.

**Generated stills — do not screenshot these.** They come from `scripts/build_charts.py` and
regenerate with the evidence, so they cannot drift. Use the **`.png`** variants on the timeline; the
`.svg` ones are for Markdown.

| Asset | Beat | Shows |
| --- | --- | --- |
| `chart-kill-storm-{dark,light}-16x9.png` | 9 | 50 interrupted · 50 resumed · 0 duplicated · 0 lost |
| `chart-lambda-timeout-{dark,light}-16x9.png` | 10 | AWS-initiated kills, all resumed |
| `chart-vector-scale-{dark,light}-16x9.png` | 11 | C-SPANN flat vs full scan climbing |
| `chart-throughput-{dark,light}-16x9.png` | 13 | agents vs completed/s, zero failures |
| `architecture-diagram-{dark,light}-16x9.png` | 4 | components — what talks to what |

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
- **The move must be motivated.** Pan down means *keep reading*. Push in means *look at this*. Hold
  means *this is dense, read it*. Anything else is fidgeting.
- **Never move on beats 6–8 or 12.** They're native video; a move there is pointless and a tell that
  something was assembled.
- **Banned outright**: spin, bounce, elastic easing, glitch and whip transitions, animated text
  pop-ins, drop shadows on stills, and more than one move per beat. Each reads as "template" and
  pulls attention off the thing being claimed.

---

## Narration script

**Generated — `scripts/generate_demo_voiceover.py` is the source of truth for this text**, not the
table below. Synthesised with **Amazon Polly** (generative engine, voice `Ruth`, `eu-central-1` —
same account and region as the Lambda). Edit the wording in the script, re-run `make voiceover`, and
paste the emitted table back here so the words, the committed MP3s and the caption track never drift.

One MP3 per beat in `assets/demo-voiceover/` as `vo_NN-slug.mp3`. Per-beat files, not one long track:
it makes the timeline deterministic, and re-cutting one beat doesn't force a full re-record.

**Word counts are the budget** — don't add words without removing others, then re-run and re-paste
the measured durations.

| Clip | Text | Words | Measured | Starts at |
| --- | --- | --- | --- | --- |
| `vo_00-problem` | The conditions that cause a production incident — a node failure, a bad deploy, memory exhaustion — are the same conditions that kill the agent responding to it. And an agent that holds its state in memory doesn't degrade gracefully. It stops. Then a human restarts the incident from zero, with no idea which remediation actions already ran. | 58 | 20.1s | 0:03 |
| `vo_01-reveal` | Continuum is an incident-response agent whose memory lives in CockroachDB instead of in the process. It runs on AWS Lambda with no provisioned concurrency, so every invocation starts cold. Which means the process is allowed to die. | 37 | 15.0s | 0:24 |
| `vo_02-architecture` | Five agents, one write path. Before any reasoning, the orchestrator's first action is always a recovery read against CockroachDB. If an incident is already open, it picks up from the durable state — never from scratch. | 36 | 13.4s | 0:40 |
| `vo_03-normal` | An alert fires. Bedrock embeds it. CockroachDB's vector index finds the closest past incident, and Claude proposes the next step. That step is committed as executing — before it runs. | 30 | 12.5s | 0:54 |
| `vo_04-kill` | Now watch. The process is killed mid-step. No graceful shutdown. No checkpoint. Nothing gets a chance to clean up. | 19 | 7.9s | 1:08 |
| `vo_05-survives` | The process is gone. The step is still there — sitting in executing, with nothing alive that owns it. That row is the agent's memory, and it outlived the agent. | 30 | 9.9s | 1:21 |
| `vo_06-resume` | A cold Lambda invocation. It reads CockroachDB first, finds the interrupted step, and re-runs that exact step. Not from scratch. Not skipped. Not duplicated. | 24 | 11.6s | 1:35 |
| `vo_07-scale` | That isn't one lucky take. Fifty interrupted incidents. Fifty clean resumes. Zero duplicated actions, zero lost steps — counted from the durable rows, not from a log. | 27 | 11.7s | 1:48 |
| `vo_08-aws` | And it isn't only our own kill switch. Here, AWS terminates the function itself, mid-step, with no signal the process can catch. All fifteen recovered, exactly once. | 27 | 11.5s | 2:01 |
| `vo_09-vector` | The memory layer scales with it. From one hundred incidents to ten thousand, CockroachDB's vector index stays flat while a full scan climbs away from it — six times faster at the top end. | 34 | 11.4s | 2:13 |
| `vo_10-mcp` | The same memory is queryable live, through CockroachDB's managed MCP server — read-only, called by the application itself. | 18 | 8.6s | 2:25 |
| `vo_11-production` | Type-checked, linted and gated in CI, with the recovery contract pinned by tests that hard-kill a real process on every push. | 21 | 8.4s | 2:35 |
| `vo_12-close` | Agents will keep dying mid-task. Continuum is the one that picks up exactly where it left off. | 17 | 5.7s | 2:44 |

**Narration spine 2:27.7** (147.7 s measured via ffprobe).

`vo_00-problem` spends the video's most valuable twenty seconds on the *problem*, not the product —
a judge who doesn't feel the problem won't care about the guarantee. It names no sponsor technology
at all, deliberately: `vo_01-reveal` then lands **CockroachDB and AWS Lambda in the same breath as
the core claim**, which is a stronger association than listing them up front would be.

---

## Final beat timeline

The cumulative column is the running total — if a beat overruns, this is where you see it before the
export does. Pads beyond the measured VO are deliberate screen time, not dead air: the silence on the
dead terminal in beat 6 and the hold on the `executing` row in beat 7 are doing the most work in the
video.

| # | Beat | VO (measured) | Visual | Motion | On-screen caption | Dur | Cum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Opening card | silent | `demo-cards/banner-{dark,light}.png` | **static** — exactly 1920×1080 | none | 3.0s | 0:03 |
| 2 | The problem | `vo_00-problem` (20.1s) | `s01-readme-top` | pan down | none | 21.5s | 0:24 |
| 3 | Reveal | `vo_01-reveal` (15.0s) | `s02-console-idle` → `s03-space-url` | static ×2 | `huggingface.co/spaces/iarjunganesh/continuum · live` | 16.0s | 0:40 |
| 4 | Architecture | `vo_02-architecture` (13.4s) | `architecture-diagram-*-16x9.png` | **static** | `5 agents · 1 write path · recovery read first` | 14.4s | 0:54 |
| 5 | Normal operation | `vo_03-normal` (12.5s) | `s04-timeline-executing` | slow push-in | `Titan embed → C-SPANN search → Claude` | 13.5s | 1:08 |
| 6 | **The kill** | `vo_04-kill` (7.9s) | **#1 live** — terminal dying mid-line | native, no move | `chaos_kill.py — SIGKILL, no graceful shutdown` | 12.9s | 1:21 |
| 7 | **State survived** | `vo_05-survives` (9.9s) | **#1 live** — the row in `executing` | native, **hold 3s+** | `status: executing — and nothing is alive` | 13.9s | 1:35 |
| 8 | **The resume** | `vo_06-resume` (11.6s) | **#1 live** — cold invocation resuming that step | native, no move | `resumed: true · same step_index · executed once` | 13.6s | 1:48 |
| 9 | Not once — fifty times | `vo_07-scale` (11.7s) | `chart-kill-storm-*-16x9.png` | **static** | `50 kills · 0 duplicated · 0 lost` | 12.5s | 2:01 |
| 10 | AWS kills it | `vo_08-aws` (11.5s) | `chart-lambda-timeout-*` → `s09-lambda-console` | static ×2 | `AWS terminated the function — it still resumed` | 12.3s | 2:13 |
| 11 | The index earns its place | `vo_09-vector` (11.4s) | `chart-vector-scale-*` → `s05-explain-plan` | static ×2 | `100 → 10,000 vectors · C-SPANN stays flat` | 12.2s | 2:25 |
| 12 | Live query over MCP | `vo_10-mcp` (8.6s) | **#2 live** — `mcp-query-take.mp4` (or `s06` still) | native, no move | `Managed MCP Server · read-only` | 9.4s | 2:35 |
| 13 | Production | `vo_11-production` (8.4s) | `s07-ci-badges` → `s08-adr-list` → `chart-throughput-*` | static, pan, static | `100% coverage · 9 ADRs · CI on every push` | 9.2s | 2:44 |
| 14 | Close | `vo_12-close` (5.7s) | `demo-cards/signoff-{dark,light}.png` | **static** | `The memory outlived the failure.` | 8.7s | **2:53** |

**Never hold a single static frame longer than ~15 s** under continuous narration — that's the real
ceiling on how long any still can sit on screen, moving or not. If the cut runs short, extend beats
7 and 9 first; if it runs long, trim beats 3 and 13 first.

---

## Assembly (Clipchamp on Win11, or CapCut)

You'll have **11 images** (opening card, `s01`–`s09` as used, the architecture PNG, four chart PNGs,
closing card) and **2 video files** (`kill-recover-take.mp4`, `mcp-query-take.mp4`).

**Before laying anything down**, set the project canvas background to match your chosen theme —
`#0d0d0d` (dark) or `#ffffff` (light) — so any letterboxed still sits on matching colour instead of
default black.

Drop in this order. Beats 6–8 come from the **same** take — trim, don't re-cut across them.

| Track pos | Beat | Asset | Motion |
| --- | --- | --- | --- |
| 1 | 1 | `banner-{dark,light}.png` | static |
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
| 12 | 12 | `mcp-query-take.mp4` | native |
| 13 | 13 | `s07-ci-badges` → `s08-adr-list` → `chart-throughput-*` | static, pan, static |
| 14 | 14 | `signoff-{dark,light}.png` | static |

Then drop the thirteen `vo_NN` clips onto the audio track underneath, each at its **Starts at** time
from the narration table.

**Transitions**: hard cuts everywhere, except a 200–300 ms cross-dissolve between the two stills
*within* beats 3, 10 and 11 — so a paired drill-down reads as navigation rather than a jump.

**Edit rhythm**: in the live footage, cut on actions rather than mid-motion; everywhere else, land
the cut on a narration phrase boundary, never mid-sentence. Because most of this timeline is stills,
the cuts carry the pace a moving cursor would otherwise carry — sloppy cut placement shows up far
more here than it would in a screen recording.

**Audio**: narration at a consistent level. **No music under beats 6–8** — the silence while the
terminal is dead is doing work; don't fill it. If you use a bed elsewhere, Clipchamp's licensed stock
only, ~17 dB under the narration, with a closing fade. **No copyrighted tracks.**

**Captions**: `assets/demo-video/continuum.srt` is generated by `make voiceover` and synced to the
measured clip timings — upload it with the video. Auto-generated captions mangle exactly the words
that matter here (*CockroachDB*, *C-SPANN*, *structlog*, *SIGKILL*). Burn in the on-screen captions
from the timeline as lower-thirds, ≤ 4 s each, one per beat.

**Watch the final cut twice before calling it done** — once with **audio off** (the story must
survive on picture and captions alone) and once with **video off** (the narration must stand up
without the pictures). Both have to pass.

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
- **Beat 12 only airs as video if you actually recorded a live query.** If you fall back to the `s06`
  still, that's fine and honest — a still of a real answer is as truthful as filming one. What's not
  allowed is a still where the *change* is the claim.
- **Never show anything resembling real infrastructure.** All services are fictional (ADR 005).
- **Don't claim multi-region.** Not implemented, explicitly out of scope — CockroachDB Basic needs
  three regions to survive a region failure and regions cannot be removed once added, so it was a
  one-way door with a recurring cost. See `submission/SUBMISSION.md` § Scope.
- **Don't record option 2 and call it option 1** (see *Which recovery to record*).
- **Re-verify beat 13's numbers on shoot day** — coverage percentage, ADR count, test count — against
  what `make coverage` and `ls docs/adr/` actually report, not from memory of an earlier run.
- **Don't show a spend figure** you haven't checked against `submission/COSTS.md` that day.

---

## If a take goes wrong

| Symptom | Fix |
| --- | --- |
| Kill landed after the step completed | Raise `STEP_EXECUTION_SECONDS`, reshoot. The window is a recording aid |
| `reasoning_source: precedent_replay` | Bedrock throttled — `make probe-bedrock`, switch `BEDROCK_REGION`, reshoot beat 5 |
| Left pane went black at the kill | You used Window Capture. Switch to **Display Capture** and reshoot |
| Console blank on first paint | Expected: `CONTINUUM_UI_LOAD_ON_OPEN=0` after the RU audit. Click Refresh before capturing |
| Resume shows a *new* incident | Correlation id differed between invocations — reuse the exact same alert |
| Terminal text unreadable at 1080p | Font below ~16 pt. Increase and reshoot; this beat only works if legible |
| Lambda invocation times out on camera | Check the function's `Timeout` wasn't left low by a benchmark run — it should be 60 s |
| Lambda resume fails on camera (`AccessDenied`, throttle, stall) | Fall back to `--via-api` for beat 8 **and** re-record `vo_06-resume` — the committed clip says "a cold Lambda invocation". `AccessDenied` is almost always the `.env` static keys outranking the profile (CLAUDE.md) |
| Recording is silent when you expected audio | Desktop Audio was disabled, not just muted. Unrecoverable — reshoot |

---

## Production checklist

**Not yet shot.** Tick these against the *exported file*, not the timeline.

**Prep**

- [ ] `make probe-bedrock` green, `reasoning_source` reads `bedrock` on screen, output saved to evidence
- [ ] `make check-drift` clean — nothing stale can appear in beat 13
- [ ] Charts present and committed (`assets/charts/*-16x9.png`, from evidence run `1f98a6fc`) —
      **do not run `make resilience-bench` today**; it aborts on a Cloud DSN and burns the demo
      cluster if forced
- [ ] `make voiceover` current — narration table in this doc matches the committed MP3s
- [ ] OBS: 1920×1080 base *and* output, 30 fps, CBR 12–16 Mbps, MKV, **mic Disabled**, desktop audio ON
- [ ] OBS: Start/Stop **hotkeys bound** — OBS's own window never appears on camera
- [ ] Display Capture (not Window Capture), Capture Cursor on
- [ ] Focus Assist on, tabs closed, bookmarks hidden, scrollback cleared, terminal ≥ 16 pt

**Shoot**

- [ ] Recording #1 is **one continuous take** covering beats 6–8, remuxed to `kill-recover-take.mp4`
- [ ] Every take **`ffprobe`d**: 1920×1080, 30/1, h264 — not the monitor's native resolution
- [ ] The interrupted step reads **`executing`** in the take — verified before cutting
- [ ] Kill is local (`--via-api` + `chaos_kill.py`); **resume is `--via-lambda`** and the dead
      terminal stays in frame. If the resume fell back to `--via-api`, `vo_06-resume` was re-recorded
      to match
- [ ] Recording #2 shot, or beat 12 consciously falls back to the `s06` still
- [ ] The remaining **8** stills captured at the right type and viewport into
      `assets/demo-video/statics/` — `s03` is already satisfied by
      `assets/provider-evidence/1080p/01.space-console-executing-banner.png`
- [ ] `make obs-assets` run, so anything used from `assets/provider-evidence/` is the 1080p variant
- [ ] One theme held throughout — UI, cards, diagram, charts

**Session C — evidence capture (not filmed)**

- [ ] `make chaos-capture-pause` run **against the Cloud cluster**, folder written, outcome `PASS`
- [ ] Shot `03` — the `executing` row in the CockroachDB console — taken **during the pause**.
      This is unrecoverable afterwards; the incident resolves on ENTER
- [ ] Shots `01`, `02`, `04`, `05` into `assets/chaos-run/local-<id>/screenshots/`, run-id prefixed
- [ ] `assets/README.md`, `assets/chaos-run/README.md` and `SUBMISSION.md` Known Gaps updated to
      the new run id, superseding `local-4789422d`

**Cut & publish**

- [ ] Canvas background set to `#0d0d0d` / `#ffffff` before assembly
- [ ] Exported file is **1920×1080, 30 fps, under 3:00** — check the *file*, not the timeline
- [ ] `continuum.srt` uploaded alongside
- [ ] Watched once with audio off, once with video off — both pass
- [ ] Watched start to finish in a phone-sized window — captions still legible?
- [ ] Uploaded **public** (not unlisted), thumbnail set to `banner-{dark,light}.png`
- [ ] Link added to the README Live Demo table, `submission/SUBMISSION.md`, and `submission/DEVPOST.md`

---

## Related

- `submission/SUBMISSION.md` — what's evidence-backed, plus the open gaps stated plainly
- `assets/provider-evidence/README.md` — console captures, and how to take the AWS ones
- `docs/RESILIENCE.md` — the numbers quoted in beats 9–11
- `docs/BENCHMARKS.md` — latency methodology and caveats
- `assets/README.md` — evidence index and capture conventions
- `assets/chaos-run/README.md` — Session C's output: folder layout and the numbered shot list
- `docs/CLUSTER_OPS.md` — which commands may touch the Cloud cluster, and why `chaos-capture` is split
- `assets/demo-voiceover/README.md` — how the narration is generated
- `submission/SUBMISSION.md` — the rules checklist this video satisfies
