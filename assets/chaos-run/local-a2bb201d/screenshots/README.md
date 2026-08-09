# Screenshots — run `a2bb201d`

Captured live during `python scripts/chaos_capture.py --pause` on **2026-08-09**, against the
CockroachDB Cloud cluster and the deployed Hugging Face Space. Incident
`6433e546-8211-479a-b0e5-2dcb6ca9e990`, correlation id `chaos-5dd7084d` — the same incident the
`evidence/*.json` in this folder describes, so every frame can be checked against the machine-read
record beside it.

All frames are unedited 1920×1080 captures with the URL bar in view. Numbering follows the shot
plan in [`../../README.md`](../../README.md).

| File | Shot | What it establishes |
| --- | --- | --- |
| `a2bb201d_00-space-console-at-rest.png` | `00` | **The console before this run existed** — `OPEN 0 · IN-FLIGHT 0 · RESOLVED 54`, green *"No steps in-flight — 0 open incidents fully checkpointed"*. Not in the original plan; it earns its place as the control for `01`, taken from the same page six minutes earlier |
| `a2bb201d_01-space-console-step-in-flight.png` | `01` | The same console with this run's incident open: `OPEN 1 · IN-FLIGHT 1`, amber *"1 remediation step in-flight (status = executing)"*, card `6433e546 · Remediating · 0/1 steps executed`. Taken **inside the pause**, with no process alive |
| `a2bb201d_02-terminal-kill-pause-and-cold-resume.png` | `02` + `04` | The whole run in one frame: `[3/6] SIGKILL delivered to pid 38600 — process is gone`, the pause, `[5/6] cold process resumed at step 0 — the exact step it died on`, `[6/6] resolved · 3 steps executed · 0 duplicated · 0 lost` |
| `a2bb201d_03-crdb-console-step-frozen-executing.png` | `03` | **The money shot.** `step_index 0 · executing · increase_database_connection_pool_size`, in Cockroach Labs' own UI, while the process that committed it is dead. This state exists only inside the `--pause` window and cannot be staged after the fact |
| `a2bb201d_05-space-console-resumed-and-resolved.png` | `05` | The console after the resume: tiles back to `OPEN 0 · IN-FLIGHT 0 · RESOLVED 55`, green banner restored, card `6433e546 · Resolved · 3/3 steps executed` carrying `⟲ resumed after kill`. Directly comparable with `01` — same page, same layout, six minutes apart |
| `a2bb201d_06-crdb-console-executing-then-executed.png` | `06` | **The strongest single frame.** The same query run twice in one session: `[1]` returns one row, `executing`; `[2]` returns three rows, all `executed`, indexes `0,1,2`. Resume *and* exactly-once, in one image, rendered by the provider |
| `a2bb201d_08-space-card-provenance-badges.png` | `08` | The full provenance chain on one card: `⟲ resumed after kill`, `claude-sonnet-4-5-20250929-v1`, `λ local`, and `⌖ recalled #1 of 5 · d=0.8313`. Each badge is read from a durable column, never inferred — and that distance is the one [`scripts/chaos_capture.py`](../../../../scripts/chaos_capture.py) predicts in its own comment for this alert text, so the code's expectation and the live console agree |

## Why there is no `04`

The shot plan lists `04` as a separate terminal frame of the cold restart. It is not missing — it is
*inside* `02`. The capture runs as one continuous process with the pause in the middle, so a
screenshot of the resume necessarily contains the kill above it, and splitting one scrollback into
two crops would show less while implying two separate events.

## Why there is no `07`

`07` is the Ask-via-MCP panel answering a live query. It was attempted here and **deliberately not
kept**: by the time the run had resolved, every incident on the cluster was closed, so the panel
correctly returned `[]`. That is a working MCP round trip and an unconvincing screenshot — a reader
cannot tell an empty answer from a broken one.

It belongs to the `lambda-<id>` run instead, taken *inside* that run's pause, where exactly one
incident is open and the panel returns the same incident the rest of that folder documents. A real
row beats a generic populated one.
