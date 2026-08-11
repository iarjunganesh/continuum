# Demo Video — Shooting Script (≤ 3 min)

> **Target 2:50–2:55** (hard cap **3:00**, disqualifying if over) · **public** on YouTube · 1920×1080 / 30 fps ·
> no copyrighted music · synthetic data only (ADR 005).
> **Status: shot, cut and published.** Committed and ready: narration
> (13 clips), captions, charts, cards, both diagrams, the CockroachDB, Space, Bedrock and Lambda
> frames under `assets/provider-evidence/` (2026-08-08) — one of which,
> `09.lambda-configuration.png`, satisfies the `s09` beat outright — every still the timeline needs
> (`s01`–`s05`, `s07`, `s08`, `s10` in [`../assets/demo-video/statics/`](../assets/demo-video/statics/)),
> the four beat outputs in [`../assets/demo-video/beats/`](../assets/demo-video/beats/), and **both
> live takes**: `kill-recover-take.mp4` (42.0s) and `mcp-query-take.mp4` (10.5s). `s06` is not needed
> — Recording #2 was shot, so the fallback it exists for never triggered.
> **Cut, exported and published 2026-08-12: https://youtu.be/LwD8__sKqa0** (2:55.7). What remains
> is not production work — confirm Visibility reads Public, confirm the caption file uploaded,
> and watch it once with audio off and once with video off.

**Time budget — kept as the plan the 2026-08-11 shoot actually ran to, not as outstanding work.** Everything
below is written to make each beat correct on the first attempt, not to be worked through in order
on the day. Plan roughly: OBS + desktop setup **30 min** · Step 0 prep **20 min** · Recording #1
**45 min** including retakes · assembly and export **90 min**. Session C and the stills are both
done, so what remains is half a day. **If you are running long, cut in this order**: Recording #2
(beat 12 falls back to the `s06` still — but that still is *not* captured, so cutting the recording
means spending ten minutes on the still instead) → beat 13's third still. **`s09` is no longer a cut
candidate** — it costs nothing, because `09.lambda-configuration.png` is already captured and
committed. **Never cut, shorten, or re-shoot-in-pieces beats 6–8.**
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

There was also a fourth thing to capture, **not part of the video at all**:

- **Session C — Evidence capture** — ✅ **done 2026-08-09, before shoot day.** Both runs are
  captured *and* screenshotted: [`../assets/chaos-run/local-a2bb201d/`](../assets/chaos-run/local-a2bb201d/)
  (a real `SIGKILL`) and [`../assets/chaos-run/lambda-0b99a950/`](../assets/chaos-run/lambda-0b99a950/)
  (AWS delivering the kill). Nothing from it appears on the timeline. **Do not re-run it on shoot
  day** — the frames are committed and the section below is kept only as the method, for if a run
  ever needs redoing. See *Session C* for why it could never have doubled as Recording #1 anyway.

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
| Output → Recording | Recording Format | **Hybrid MP4** | A crash — or a hard-kill of the *wrong* window — leaves a classic MP4 corrupt, because it is finalised on stop. Hybrid MP4 writes recovery data as it goes, so it survives that **and** needs no remux, unlike MKV |
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

**After each take**: copy the file straight to the name this script gives it, in
`assets/demo-video/`. There is no remux step — that is the reason for Hybrid MP4 over MKV. If your
OBS is old enough to lack Hybrid MP4, record MKV and File → **Remux Recordings** afterwards; never
record a *classic* MP4, which is finalised on stop and is therefore unrecoverable if OBS dies.

### Desktop hygiene — do this before the first take, not between takes

**Applied for the 2026-08-11 shoot.** Ticked against the exported cut rather than from memory:
every frame was swept, and no notification, unrelated tab, personal content, credential or
connection string appears in any of them.

- [x] **Windows Focus Assist → Do Not Disturb.** One Teams toast in the middle of the kill beat
      costs you the whole take.
- [x] Close Slack, mail, Discord, Steam, and anything with a badge that can update.
- [x] Single monitor, or at minimum make sure the captured display has nothing personal on it.
- [x] Browser: a clean profile or a new window — **bookmarks bar hidden** (`Ctrl+Shift+B`), no
      extension icons you can't explain, **and every tab closed except the ones being filmed**. A
      row of unrelated tabs is the single most common thing that makes a demo look unrehearsed.
- [x] Desktop wallpaper: neutral. It will be visible for a moment somewhere.
- [x] Terminal: **one full-screen window**, font **16–18 pt**, high-contrast theme, **scrollback
      cleared** (`Clear-Host`). The structlog JSON is the star of beats 6–8; if a judge can't read it
      at 1080p in a small player, the beat has failed.
- [x] Secrets off screen: `.env` closed, connection strings out of scrollback, no cluster console
      tab showing credentials.
- [ ] ~~Commands **pre-typed into shell history** so you recall them with ↑~~ — **don't.** Pre-typing
      cost a stray incident on 2026-08-11: an Enter instead of `Esc` fired an alert against the demo
      cluster minutes before rolling, and it had to be driven to `resolved` before the take could
      start. Paste each command from the runbook when you reach it instead. Left unticked because
      the practice is superseded, not completed.

**Mouse discipline** — move **deliberately**, click **confidently**, **pause** on anything a judge is
meant to read. No rapid scrolling, no hovering, no idle cursor circling, no tab-switching mid-beat.
This is most of what separates footage that reads as polished from footage that reads as a rehearsal.

---

## Step 0 — one-time prep, before recording anything

> **Set `AWS_PROFILE` in the recording shell, before anything else.** `--via-lambda` calls
> `lambda:InvokeFunction`, and the **default identity in `~/.aws/credentials` is
> `continuum-bedrock`, which is Bedrock-invoke-only by design** — it gets
> `AccessDeniedException: not authorized to perform: lambda:InvokeFunction`. That command is the
> **resume in Recording #1**, so the failure lands on camera in the one take that must not be cut,
> and it reads as the recovery itself failing. Hit this for real on 2026-08-08.
>
> ```powershell
> Remove-Item Env:AWS_ACCESS_KEY_ID     -ErrorAction SilentlyContinue
> Remove-Item Env:AWS_SECRET_ACCESS_KEY -ErrorAction SilentlyContinue
> $env:AWS_PROFILE = "continuum-admin"
> python scripts/demo_run.py --tick --via-lambda --new   # throwaway — see below for what proves it
> ```
>
> **`runtime` is persisted, not printed.** That command's JSON carries `correlation_source` and
> `reasoning_source` but no `runtime` field, so a successful Lambda invocation looks identical to a
> local one on stdout. The durable row is the authority — `remediation_steps.detail->>'runtime'`
> reads `lambda` only when the step actually executed inside the function, because it comes from
> Lambda's own `AWS_LAMBDA_FUNCTION_NAME`. Check the console's `λ runtime` badge, or query it.
> What the command *does* prove immediately is the negative: an `AccessDeniedException` here means
> the profile did not take.
>
> Clearing the static keys first is not optional: `.env` exports them for the Bedrock-only user and
> **boto3 ranks static environment keys above a named profile**, so setting the profile alone leaves
> you on the identity that cannot invoke. Same trap as `docs/DEPLOY.md`, different command.

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
> **already generated and committed** from evidence run `e765a3c5`; they cannot drift, because
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
| Format / bitrate | Hybrid MP4, CBR 12–16 Mbps |
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
3. Copy the file out of the recording folder to **`assets/demo-video/kill-recover-take.mp4`**. <!-- drift-allow-path: the take does not exist until this step is performed -->

   Copy, don't move — the original stays put until the cut is exported and you know you're done.
4. Verify what you actually captured before you trust it:

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

Free and retakeable — ~15 seconds, one button click, as many attempts as you like. "Optional" here
means *first to cut if the day runs out*, not *skip by default*: `s06` is not captured, so cutting
this take costs a still rather than saving one. Shoot it.

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

**Set browser page zoom to 150% before rolling.** Beats 3 and 5 are rendered from 1200-viewport
DPR-2 captures downscaled to 1920, so the console appears there at ~1.6× life size. A live recording
in a 1920 window at 100% zoom shows it at 1.0×, and beat 12 would visibly jump against the beats
either side of it. 150% is Edge's nearest step and closes the gap. Same window size as take #1.

### Shoot it immediately after Recording #1 — the incident has to be open

`ask_via_mcp()` calls `list_open_incidents()`
([`../ui/app.py`](../ui/app.py)), so with a clean cluster it returns `[]` — an empty array on screen
under narration saying *"you can simply ask it"*, which reads as broken rather than honest.

After Recording #1's resume the incident is **still open**: step 0 is `executed`, steps 1–2 are not,
and the state is `remediating`. So roll #2 straight away and the answer names *the incident the
judge has just watched being killed and recovered*. That continuity is worth more than any question
you could compose, and it costs nothing — it is the same incident, not a second one.

Resolve it afterwards, not before: `python scripts/demo_run.py --tick --via-lambda` until the JSON
reads `"state": "resolved"`, then stop. One tick past resolved opens a fresh incident.

### The take — beat 12

1. Gradio console open, previous answer cleared, page zoom **150%**.
2. Start OBS (hotkey).
3. Click **"Ask via MCP: what's open right now?"** — it is a **button, not a text field**. Nothing
   is typed on camera, so there is no wording to pre-decide and no typo to retake for.
4. Let the JSON render fully. **Pause on it** for 2–3 seconds; that pause is the beat.
5. Stop with the hotkey, wait ~2 s, copy to **`assets/demo-video/mcp-query-take.mp4`**. <!-- drift-allow-path: the take does not exist until this step is performed -->

6. `ffprobe` it exactly as above — same 1920×1080 / 30 fps expectation.

---

## Session C — Evidence capture ✅ done 2026-08-09 (not filmed)

**This is finished — it is not shoot-day work.** Kept as the method, because a run may need
redoing and the timing is easy to get wrong.

`make chaos-capture-pause` produces the judge-facing artifact the *repo* needs: a
`assets/chaos-run/local-<id>/` folder holding a provenance manifest, the three phase snapshots read
straight out of CockroachDB, the orchestrator's own structlog, the Bedrock probe — and the console
screenshots that go with them. `make chaos-capture-lambda --pause` does the same against the
**deployed** function, with AWS delivering the kill via a lowered timeout. **None of it lands on the
video timeline.** It is what a judge opens when they want to verify the claim without watching
anything.

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

Done on 2026-08-09: `local-a2bb201d` and `lambda-0b99a950`, seven frames each, both with a
`screenshots/README.md` mapping frame to claim. They supersede `local-4789422d` and
`lambda-c81826e7`, which keep complete evidence JSON and empty `screenshots/` folders — they were
unattended, and the interrupted state they captured is long resolved. Those two are kept rather
than deleted: two independent passes of the same contract is a stronger claim than one.

Any future run repeats that: update `assets/README.md`, `assets/chaos-run/README.md` and the Known
Gaps row in [`SUBMISSION.md`](SUBMISSION.md) to the new id, and **declare every new screenshot in
[`../scripts/redact_evidence.py`](../scripts/redact_evidence.py)** — `make redact-evidence --check`
fails on an undeclared file, which is what stops a raw window capture shipping with a real person's
photograph or an AWS account id in the browser chrome.

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
PNG, comfortably above the 1920 you need.

**Capture the app's own pages at 1200 as well** — the Gradio console is *not* full-bleed, which cost
a re-shoot on 2026-08-11. Its container is ~1115 CSS px wide and **left-aligned**, so at a 1920
viewport the content occupied 58% of the frame with the right 40% blank white — the same failure the
paragraph above describes for GitHub. At 1200 it fills ~80% with even gutters, and the incident cards
reflow 3-up → 2-up, which makes the alert text and provenance badges markedly more legible. Don't
also change page zoom; viewport width alone does it, and stacking both makes the result hard to
predict.

Save everything to `assets/demo-video/statics/`.

**All of these are captured** — `s01`–`s05`, `s07`, `s08` on 2026-08-11 and `s10` on 2026-08-12 —
except `s06`, which was only needed if Recording #2 were cut, and it was not. `s09` never needed a capture at all — `09.lambda-configuration.png` satisfies it outright; see
*Already captured: provider evidence* below. The table records how each was taken, so a re-shoot
reproduces it rather than re-deriving it.

| Still | Beat | Type | Viewport | What to capture | Move |
| --- | --- | --- | --- | --- | --- |
| `s01-readme-top` | 2 | A | 1280 | README from the banner through "The Problem" — cropped out of one signed-out full-page capture, along with `s07` and `s08`. Sign out first: the signed-in view shows `Settings`, `Unpin` and an edit pencil no judge sees. Note DevTools caps a full-page capture at 16384 px, which truncates this README below *Live Demo* — harmless, since all three crops sit above the cut | pan down |
| `s02-console-idle` | 3 | A | 1200 | Gradio console, incidents listed, nothing in flight. The green *"No steps in-flight — 0 open incident(s) fully checkpointed"* banner is what makes it read as idle rather than unloaded — click **Refresh now** first, the panels are blank on first paint by design | static |
| `s03-space-url` | 3 | B | — | Space at its real URL, **address bar in frame**, ideally with a step in-flight. The frame that used to satisfy this was deleted on 2026-08-08 as stale — its KPI tiles and cards predated the provenance badges, so beside the current console it read as a different app. No frame in `assets/provider-evidence/` shows the **Space's** URL in an address bar either — the AWS and CockroachDB frames show their own consoles' URLs, not this one — so this single screenshot closes both gaps | static |
| `s04-timeline-executing` | 5 | A | 1200 | A step mid-flight — the amber *"1 remediation step in-flight (status = `executing`)"* banner with `IN-FLIGHT NOW 1`. Bedrock is attested by the **model badge**, not a raw field: a step that fell back to precedent replay names no model, so `claude-sonnet-4-5-…` on a step at `0/1` proves the proposal came from Bedrock, and `d=…` renders only beside the embedding model that produced it | slow push-in |
| `s05-explain-plan` | 11 | A/B | — | `EXPLAIN` showing `vector search … prefix spans`. Taken from a **terminal**, not the Cloud console: the 1024-dim vector literal makes the console echo a screen-filling wall of `0.01,…` above its own result. Suppress the trailing `index recommendations` block — the planner suggests a *different* index, which under a caption saying "the index earns its place" reads as CockroachDB disagreeing with you | static |
| `s06-mcp-panel` | 12 | A | 1200 | Gradio "Ask via MCP" with a live answer — **fallback if Recording #2 is skipped**. The only still not captured, because it is only needed in that case | static |
| `s07-ci-badges` | 13 | A | 1280 | README badge rows — CI green, coverage, versions | static |
| `s08-adr-list` | 13 | A | 1280 | The ten-row ADR table | pan down |
| `s09-lambda-console` | 10 | B | — | AWS console: `continuum-orchestrator`, no provisioned concurrency. **Already captured** — use `assets/provider-evidence/09.lambda-configuration.png` | static |
| `s10-codecov` | 13 | A | 1400 | Codecov's page for the repo, corroborating the `100% coverage` the beat-13 caption claims. **Click "Hide charts" first**: the chart block is ~930px of mostly-empty grey, and with it the page is ratio 1.12 — no 16:9 crop can hold both the coverage figure and the file table. Hidden, the page is 1.77 and everything fits. Capture **signed out**: `Log in` in the nav and `Viewing as visitor` beside the repo name show a judge can open the same page, and there is then no avatar to mask. Type A at DPR 2 rather than a window capture — the same figure renders ~1.8× larger, and at two seconds on screen that is the difference between reading it and not | static |

### Already captured: provider evidence

`assets/provider-evidence/` holds console captures taken from **Cockroach Labs', Hugging Face's and
AWS's own UIs** — screens this project cannot fake. They were captured as repo evidence first, so
most have no beat and belong in the README and on Devpost rather than in a 3-minute video. Four of
them earn screen time, and `09` closes the `s09-lambda-console` still outright — that beat needs no
new capture.

`assets/provider-evidence/` was re-captured on **2026-08-08** and the browser-chrome frames are
already exactly **1920×1080**, so they drop straight onto the timeline with no intermediate step.
The generated `1080p/` folder was deleted for that reason — it duplicated frames that no longer
needed normalising. Two files still do, because they are full-page captures rather than viewport
ones: `01.space-console-full-page.png` (1920×**5412**) and `00.space-first-paint.png`
(1920×**2728**). Run `python scripts/build_obs_assets.py` to regenerate the folder when you need
those as pans; it pads short captures and pans tall ones, and never downscales.

| Asset | Use | Why it earns the time |
| --- | --- | --- |
| `03.crdb-cluster-overview-eu-central-1.png` | **Beat 13**, after `s07-ci-badges` | `Plan Basic · Cloud AWS · Region Frankfurt (eu-central-1) PRIMARY · v26.2.5`, with the cluster's creation date and live RU burn, in Cockroach Labs' own UI. The "CockroachDB deployed on AWS" requirement corroborated by a screen we don't control. Exactly 1920×1080 — hold static |
| `05.crdb-sql-activity-fingerprints.png` | **Beat 13** alternative | Real statement fingerprints with execution counts — the single write path as actual traffic — and the correlation query visible in its `WITH nearest AS (… embedding <->…)` CTE form. Contention time 0.0 ns on every row |
| `01.space-console-full-page.png` | **Beat 3** alternative to `s02-console-idle` | The entire console in one tall image. Needs a pan (or a crop) — it is 5412 px tall. **It shows a step in flight**, so it reads as beat 3 *or* beat 5, not as "idle" |
| `09.lambda-configuration.png` | **Beat 10**, satisfies `s09-lambda-console` | `Provisioned concurrency (0) — No configurations`, in AWS's own console. ADR 002's guarantee rests on an absence, and this is the only page that states it. Exactly 1920×1080 — hold static |
| `11.lambda-log-stream-recovery.png` | **Beat 10** alternative | One CloudWatch log stream: `INIT_START` on `python:3.14`, then `recovered_incident_state` reads carrying `last_step_index`. A cold environment reading incident state back out of CockroachDB, in Lambda's own log. Dense — only use it if you can hold it long enough to read one JSON block |
| `00`, `04`, `06`, `07`, `08`, `10` | **not in the video** | The blank first paint, the Metrics dashboard, job history, the MCP service account, and the two CloudWatch data tables (Bedrock invocations/latency, Lambda invocations/errors). Repo and Devpost evidence; the tables in particular are unreadable at video scale — the generated charts carry those numbers instead |

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

## The first thirty seconds — what a judge knows, and when

`vo_00-problem` deliberately names no product and no technology, so for the first twenty seconds the
**picture and the captions** are the only things answering *"what is this?"*. That is a choice, not
an oversight — but it only works if those two actually carry it.

- **Beat 2's move is built around it.** `beat02-readme.mp4` opens on the logo and the README's
  one-line thesis, then settles at **0:12–0:15** on the frame holding *"An autonomous
  incident-response agent that resumes the exact step it was killed on — because its memory lives in
  CockroachDB, not in the process"* together with the full badge stack: `AWS Lambda` · `Titan` ·
  `Claude Sonnet 4.5` · `CockroachDB Cloud` · `Distributed Vector Indexing C-SPANN 1024d` ·
  `Managed MCP Server`. A constant-speed scroll would put that block on screen in passing for two
  seconds. It is the "what is it" frame, so it is held.
- **Beats 1 and 2 carry captions for the same reason.** They used to read `none`. A judge watching
  with sound off — and many do, on a first pass through a pile of submissions — now gets the
  category, the runtime and the memory layer inside the first six seconds.

By 0:24 the answer has arrived three independent ways: in text, in picture, and then in
`vo_01-reveal` saying it out loud. Nothing was cut from the narration to achieve that, and the
2:55 total is unchanged.

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
| `vo_01-reveal` | Continuum is an incident-response agent whose memory lives in CockroachDB, not in the process. On AWS Lambda, it never trusts what's in memory — every invocation re-reads its state from the database first. So the process is allowed to die. | 40 | 15.5s | 0:24 |
| `vo_02-architecture` | Five agents, and only one of them is allowed to write. Every fact about an incident goes through a single module into one database — so whatever picks that incident up next can trust everything it reads. | 37 | 11.5s | 0:41 |
| `vo_03-normal` | An alert fires. Bedrock turns it into a vector, CockroachDB finds the closest incident it's seen before, Claude proposes the next step. And here's what matters — the step is written down as executing before it runs, not after. | 39 | 14.6s | 0:53 |
| `vo_04-kill` | Now watch. The process is killed mid-step. No graceful shutdown. No checkpoint. Nothing gets a chance to clean up. | 19 | 7.9s | 1:12 |
| `vo_05-survives` | The process is gone. The step is still there — sitting in executing, with nothing alive that owns it. That row is the agent's memory, and it outlived the agent. | 30 | 9.9s | 1:22 |
| `vo_06-resume` | A cold Lambda invocation — a different machine, in a different region, with no memory of this. It reads CockroachDB first, finds the interrupted step, and re-runs it. Not from scratch. Not skipped. Not duplicated. | 35 | 14.3s | 1:35 |
| `vo_07-scale` | That isn't one lucky take. Fifty interrupted incidents. Fifty clean resumes. Zero duplicated actions, zero lost steps — counted from the durable rows, not from a log. | 27 | 11.7s | 1:51 |
| `vo_08-aws` | And it isn't only our own kill switch. Here, AWS terminates the function itself, mid-step, with no signal the process can catch. All fifteen recovered, exactly once. | 27 | 11.5s | 2:03 |
| `vo_09-vector` | And the memory scales with it. From one hundred incidents to ten thousand, CockroachDB's vector index stays flat while a full scan climbs away — seven and a half times faster. | 31 | 11.2s | 2:15 |
| `vo_10-mcp` | And because it's all one database, you can simply ask it — the app querying its own memory, live, through CockroachDB's managed MCP server. | 24 | 9.1s | 2:27 |
| `vo_11-production` | Type-checked, linted and gated in CI, with the recovery contract pinned by tests that hard-kill a real process on every push. | 21 | 8.4s | 2:37 |
| `vo_12-close` | Agents will keep dying mid-task. Continuum is the one that picks up exactly where it left off. | 17 | 5.7s | 2:48 |

**Narration spine 2:31.4** (151.4 s measured via ffprobe).

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
| 1 | Opening card | silent | `demo-cards/banner-{dark,light}.png` | **static** — exactly 1920×1080 | `Incident-response agent · memory outlives the process` | 3.0s | 0:03 |
| 2 | The problem | `vo_00-problem` (20.1s) | **`beats/beat02-readme.mp4`** | pre-rendered — see below | `Runs on AWS Lambda · state in CockroachDB · Bedrock reasoning` | 21.5s | 0:24 |
| 3 | Reveal | `vo_01-reveal` (15.5s) | **`beats/beat03-console.mp4`** → `s03-space-url` | static ×2 | `huggingface.co/spaces/iarjunganesh/continuum · live` | 16.5s | 0:41 |
| 4 | Architecture | `vo_02-architecture` (11.5s) | `architecture-diagram-*-16x9.png` | **static** | `5 agents · 1 write path · recovery read first` | 12.5s | 0:53 |
| 5 | Normal operation | `vo_03-normal` (14.6s) | **`beats/beat05-timeline.png`** (2400×1350) | **editor zoom**, 100% → 105% — rendering it shimmered, see `beats/README.md` | `Titan embed → C-SPANN search → Claude` | 15.6s | 1:09 |
| 6 | **The kill** | `vo_04-kill` (7.9s) — starts at 1:12.0 | **#1 live** — clip 0:00–0:12.4, terminal dying mid-line at 0:11 | native, no move | `chaos_kill.py — SIGKILL, no graceful shutdown` | 12.4s | 1:21 |
| 7 | **State survived** | `vo_05-survives` (9.9s) | **#1 live** — clip 0:12.4–0:25.4, the row in `executing` | native, **hold 3s+** | `status: executing — and nothing is alive` | 13.0s | 1:34 |
| 8 | **The resume** | `vo_06-resume` (14.3s) — starts at 1:35.0 | **#1 live** — clip 0:25.4–0:42.0, JSON lands at 0:36 | native, no move | `resumed: true · same step_index · executed once` | 16.6s | 1:51 |
| 9 | Not once — fifty times | `vo_07-scale` (11.7s) | `chart-kill-storm-*-16x9.png` | **static** | `50 kills · 0 duplicated · 0 lost` | 12.3s | 2:03 |
| 10 | AWS kills it | `vo_08-aws` (11.5s) | `chart-lambda-timeout-*` → `s09-lambda-console` | static ×2 | `AWS terminated the function — it still resumed` | 12.1s | 2:15 |
| 11 | The index earns its place | `vo_09-vector` (11.2s) | `chart-vector-scale-*` → `s05-explain-plan` | static ×2 | `100 → 10,000 vectors · C-SPANN stays flat` | 11.8s | 2:27 |
| 12 | Live query over MCP | `vo_10-mcp` (9.1s) | **#2 live** — `mcp-query-take.mp4` 0:00.8–0:10.5 | native, no move | `Managed MCP Server · read-only` | 9.7s | 2:37 |
| 13 | Production | `vo_11-production` (8.4s) | `s07-ci-badges` → **`s10-codecov`** → **`beats/beat13-adr.mp4`** → `chart-throughput-*` | static, static, pre-rendered pan, static | `100% coverage · 10 ADRs · CI on every push` | 11.0s | 2:48 |
| 14 | Close | `vo_12-close` (5.7s) | `demo-cards/signoff-{dark,light}.png` | **static** | `The memory outlived the failure.` | 7.7s | **2:56** |

Beats 6–8 carry **measured** durations, not budgeted ones: `kill-recover-take.mp4` is 42.0s and the
three beats consume it contiguously, so they cannot sum to anything else. Two voiceover clips start
*after* their beat does, because the picture has a fixed landmark the narration has to meet —
`vo_04-kill` ends as the terminal dies at 1:20.1, and `vo_06-resume` is 10.1s in when the resume JSON
renders at 1:45.1. Every other clip starts on its beat boundary.

**Never hold a single static frame longer than ~15 s** under continuous narration — that's the real
ceiling on how long any still can sit on screen, moving or not. If the cut runs short, extend beats
7 and 9 first; if it runs long, trim beats 3 and 13 first.

---

## Assembly (Clipchamp on Win11, or CapCut)

You'll have **13 images** (opening card, `s03`, `s05`, `s07`, `s10`, `beat05-timeline.png`, the
architecture PNG, four chart PNGs, the Lambda console frame, closing card) and **5 video files**
(three beat clips, `kill-recover-take.mp4`, `mcp-query-take.mp4`). `s01`, `s02`, `s04` and `s08` are
not placed directly — they are the sources the beat clips were rendered from.

**Before laying anything down**, set the project canvas background to match your chosen theme —
`#0d0d0d` (dark) or `#ffffff` (light) — so any letterboxed still sits on matching colour instead of
default black.

Drop in this order. Beats 6–8 come from the **same** take — trim, don't re-cut across them.

| Track pos | Beat | Asset | Motion |
| --- | --- | --- | --- |
| 1 | 1 | `banner-{dark,light}.png` | static |
| 2 | 2 | `beats/beat02-readme.mp4` | pre-rendered |
| 3 | 3 | `beats/beat03-console.mp4` → `s03-space-url` | pre-rendered, static |
| 4 | 4 | `architecture-diagram-{dark,light}-16x9.png` | static |
| 5 | 5 | `beats/beat05-timeline.png` | **editor zoom** 100% → 105% |
| 6 | **6** | **`kill-recover-take.mp4`** — the kill | native |
| 7 | **7** | **same take** — the `executing` row | native, hold |
| 8 | **8** | **same take** — the resume | native |
| 9 | 9 | `chart-kill-storm-*-16x9.png` | static |
| 10 | 10 | `chart-lambda-timeout-*` → `s09-lambda-console` | static ×2 |
| 11 | 11 | `chart-vector-scale-*` → `s05-explain-plan` | static ×2 |
| 12 | 12 | `mcp-query-take.mp4` | native |
| 13 | 13 | `s07-ci-badges` → `s10-codecov` → `beats/beat13-adr.mp4` → `chart-throughput-*` | static ×2, pre-rendered, static |
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
- **Beat 12 airs as video because the live query was recorded.** Had it fallen back to the `s06`
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

**Shot, cut and published 2026-08-12** — https://youtu.be/LwD8__sKqa0. Ticked against the
*exported file* and the durable rows, not against the timeline. Items that could not be
verified from outside YouTube Studio, or that were simply not done, are left unticked and say so.

**Prep**

- [x] **`$env:AWS_PROFILE = "continuum-admin"` set in the recording shell, static keys cleared** —
      and it mattered: the throwaway `--via-lambda` tick returned `AccessDeniedException` from a
      second pane that had not had the block applied. Caught in rehearsal rather than on camera,
      which is what that step exists for. Note `runtime` is **persisted, not printed** — the JSON
      shows `correlation_source`/`reasoning_source`; `runtime: lambda` is read from the durable row
- [x] `make probe-bedrock` green **2026-08-11** — OK on all five candidate regions × both models;
      every tick that day returned `correlation_source`/`reasoning_source` of `bedrock`
- [x] `make check-drift` clean before the shoot and again before this release
- [x] Charts present and committed (`assets/charts/*-16x9.png`, from evidence run `e765a3c5`) —
      and `make resilience-bench` was **not** run on shoot day, so the demo cluster was never burned
- [x] `make voiceover` current — regenerated with `--table` after the cut, so the caption track
      matches the exported audio and no clip was re-synthesised under a finished video
- [x] OBS: 1920×1080 base *and* output, 30 fps, CBR 16 Mbps, Hybrid MP4, mic Disabled, desktop
      audio ON — confirmed by `ffprobe` on both raw takes, not by trusting the settings dialog
- [x] OBS: Start/Stop hotkeys bound. OBS *did* appear at the head and tail of both raw takes and
      was trimmed out; the exported cut was swept frame by frame and contains none
- [x] Display Capture (not Window Capture), Capture Cursor on — the killed pane stays visible
- [x] Focus Assist on, tabs closed, bookmarks hidden, scrollback cleared, terminal ≥ 16 pt — no
      notification or stray window appears in either take

**Shoot**

- [x] Recording #1 is **one take** covering beats 6–8, saved as `kill-recover-take.mp4` (42.0s).
      One splice, at 0:06, removes idle *before* the kill; pane 1 is frozen at
      `step_checkpoint_start` across it, so the cut is invisible. **Nothing is spliced between
      the kill and the resume** — that stretch is untouched, and the dead terminal holds for 13s
- [x] Every take **`ffprobe`d**: 1920×1080, 30/1, h264 — both takes and the final cut
- [x] The interrupted step read **`executing`** in CockroachDB while the take was still open —
      queried directly, not inferred from the footage
- [x] Kill is local (`--via-api` + `chaos_kill.py`); **resume is `--via-lambda`** and the dead
      terminal stays in frame throughout. No fallback was needed, so `vo_06-resume` stands as
      recorded. The durable row records `runtime: lambda`, taken from the function's own
      `AWS_LAMBDA_FUNCTION_NAME` — so the resume provably executed inside the deployed function
- [x] Recording #2 shot (10.5s), immediately after #1 while that incident was still open — so
      the MCP answer names the incident the judge has just watched being killed and recovered
- [x] Stills captured into `assets/demo-video/statics/` — **`s01`–`s05`, `s07`, `s08`, `s10` on
      2026-08-11/12**, and `s09` served by `provider-evidence/09.lambda-configuration.png`. Every one
      declared in `scripts/redact_evidence.py`; `s03` carries the only mask (the signed-in avatar,
      measured off that file). `s06` is deliberately not captured — it is the Recording #2 fallback,
      and #2 was shot
- [x] `python scripts/build_obs_assets.py` **not needed** — beat 3 uses `beats/beat03-console.mp4`,
      rendered from `s02`, not the full-page provider frame
- [x] One theme held throughout — light, across UI, cards, diagram and charts

**Session C — evidence capture (not filmed)** — ✅ **complete 2026-08-09, nothing to do on shoot day**

- [x] `make chaos-capture-pause` run **against the Cloud cluster**, folder written, outcome `PASS`
      — `local-a2bb201d`, and `lambda-0b99a950` via `make chaos-capture-lambda --pause`
- [x] Shot `03` — the `executing` row in the CockroachDB console — taken **during the pause**, in
      both runs. This is unrecoverable afterwards; the incident resolves on ENTER
- [x] Seven frames per run into `assets/chaos-run/<id>/screenshots/`, run-id prefixed, each with a
      README mapping frame to claim
- [x] `assets/README.md`, `assets/chaos-run/README.md` and `SUBMISSION.md` Known Gaps updated to
      the new run ids
- [x] Every frame declared in `scripts/redact_evidence.py`; `make redact-evidence --check` green

**Cut & publish**

- [ ] Canvas background set to `#0d0d0d` / `#ffffff` before assembly — **not done.** The editor
      canvas was left at its default dark grey, which is why the cut opens with a ~0.75s fade up
      from dark and carries a 0.13s dip through black at 2:48 going into the closing card. Both
      were measured with `blackdetect` and judged acceptable — a fade into a closing card is
      ordinary grammar — but re-exporting for it would have cost a generation of picture quality
      for two fifths of a second. Left unticked because it was not done, not because it was fine
- [x] Exported file is **1920×1080, 30 fps, 2:55.7** — `ffprobe`d on the file. Audio normalised
      to **−14 LUFS / −1.5 dBTP** (YouTube's own target; the export measured −24.1 LUFS, and
      YouTube only turns loud content down, never up) with the video stream copied — MD5 of the
      video stream is identical before and after, so the picture was not re-encoded
- [ ] `continuum.srt` uploaded alongside — **confirm in YouTube Studio → Subtitles.** Auto-captions
      mangle *CockroachDB*, *C-SPANN*, *structlog* and *SIGKILL*, which is most of the claim
- [ ] Watched once with audio off, once with video off — both pass
- [ ] Watched start to finish in a phone-sized window — captions still legible?
- [ ] Uploaded **public** (not unlisted), thumbnail set to `banner-light.png` — an unauthenticated
      fetch with no cookies resolves the title and channel, which proves it is **not private**.
      Public and Unlisted are indistinguishable from outside YouTube Studio, so this stays
      unticked until the Visibility radio is read directly
- [x] Link added to the README Live Demo table and its `▶ Watch` badge, `submission/SUBMISSION.md`,
      `submission/DEVPOST.md` and `assets/demo-video/README.md`; the Devpost mirror regenerated

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
