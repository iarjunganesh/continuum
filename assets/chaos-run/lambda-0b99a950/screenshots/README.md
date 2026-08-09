# Screenshots — run `0b99a950`

Captured live during `python scripts/chaos_capture.py --via-lambda --profile continuum-admin
--pause` on **2026-08-09**, against the **deployed** `continuum-orchestrator` function
(`CodeSha256 FM6pWpg…`, the 2026-08-08 build) and the CockroachDB Cloud cluster behind it.
Incident `5b130dad-0cd3-4c56-99e6-e81aa5cb6a63`, correlation id `chaos-lambda-f6d562b7` — the same
incident this folder's `evidence/*.json` describes.

**Nothing here staged a failure.** The function's own timeout was lowered below its
step-execution window, so **AWS terminated the invocation mid-step** — no signal the runtime can
catch, no cleanup, no checkpoint — and the resume is a second cold invocation of the same
function. All frames are unedited 1920×1080 captures with the URL bar in view.

| File | Shot | What it establishes |
| --- | --- | --- |
| `0b99a950_01-space-console-step-in-flight.png` | `01` | `OPEN 1 · IN-FLIGHT 1` with the incident frozen. The card carries **`λ lambda`** while the card beside it — the local run from twenty minutes earlier — carries `λ local`: the same contract, two execution environments, one frame |
| `0b99a950_02-terminal-aws-kill-and-cold-resume.png` | `02` + `04` | `[3/6] AWS terminated the invocation mid-step (timeout 6s) — no catchable signal`, then `[5/6] a cold invocation resumed at step 0 — the exact step AWS killed` and `[6/6] resolved · 3 steps executed · 0 duplicated · runtime ['lambda']` |
| `0b99a950_03-crdb-console-step-frozen-executing-runtime-lambda.png` | `03` | The frozen row, with `runtime` pulled out of the durable `detail` column: `0 · executing · … · lambda`. The row itself attests where it ran — read from the function's own `AWS_LAMBDA_FUNCTION_NAME`, never from config |
| `0b99a950_05-space-console-resumed-resolved-with-lambda-badge.png` | `05` + `08` | After the resume: `OPEN 0 · IN-FLIGHT 0 · RESOLVED 56`, card `5b130dad · Resolved · 3/3 steps executed` carrying `⟲ resumed after kill`, `λ lambda` and `⌖ recalled #1 of 5 · d=0.8313` |
| `0b99a950_06-crdb-console-executing-then-executed-runtime-lambda.png` | `06` | The same query twice in one session: `[1]` one row `executing / lambda`, `[2]` three rows `executed / lambda`. Resume, exactly-once, **and** the runtime, in a single provider-rendered frame |
| `0b99a950_07-space-mcp-answering-live.png` | `07` | The Managed MCP Server returning `incident_id 5b130dad-… · state remediating · opened_at 18:43:24Z` — taken *inside* the pause, so it is the frozen incident itself rather than a generic populated answer (ADR 003) |
| `0b99a950_09-cloudwatch-timeout-then-cold-recovery-read.png` | `09` | **AWS stating it, in its own console.** `INIT_START python:3.14` → `REPORT … Status: timeout` → a *second* `INIT_START` in a **different log stream** → `recovered_incident_state … last_step_status: "executing"`. The stream name column changing is what makes "a fresh execution environment" visible rather than asserted |

## Why there is no separate `04` or `08`

`04` (the cold restart) is inside `02` — one continuous process, so a screenshot of the resume
necessarily carries the kill above it. `08` (the recall badge) is inside `05` — the card's full
badge row was in frame, so a second file would duplicate pixels rather than add evidence.

## Redaction

Every frame here has been through [`scripts/redact_evidence.py`](../../../../scripts/redact_evidence.py),
which masks exactly two things and records why: the signed-in user's profile photograph in the
browser toolbar, and — on `09`, the only AWS-console frame — the account id in the top-right
tooltip. The account id's box on the Logs *search* page had to be measured separately: the
existing box for the Logs *log-events* page stops three pixels short of the closing parenthesis on
this layout. No metric, timestamp, identifier, query text or status is touched.
