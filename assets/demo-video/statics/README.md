# Static frames for the demo video

Still images cut into the video's beats — console captures, terminal frames, evidence stills — as
opposed to the recorded screen footage itself. `submission/DEMO_SCRIPT.md` owns which beat uses
what.

**Anything that lands here is judge-facing.** A frame on screen in a submitted video is as public
as a file in [`../../provider-evidence/`](../../provider-evidence/), so this folder is covered by
[`scripts/redact_evidence.py`](../../../scripts/redact_evidence.py): every PNG must be declared
there before `make redact-evidence --check` will pass, with an empty region tuple if it genuinely
needs no mask. That is deliberate friction — it means the first capture dropped in here forces a
decision about the browser chrome it carries, rather than shipping because nobody looked.

Raw window captures on this machine carry two things worth deciding about:

- the signed-in user's **profile photograph** in the browser toolbar, at a fixed position in any
  1920×1080 Edge window;
- on AWS console pages, the **account id**, both in the top-right account tooltip and inside any
  ARN the page prints.

Neither is load-bearing for anything the video claims. Terminal captures carry neither.

## Inventory — captured 2026-08-11

Sizes are the committed pixels. Anything wider than 1920 was captured at DPR 2 and carries the
headroom its move needs; anything exactly 1920×1080 is held static, because a still with no spare
pixels can only be upscaled.

| File | Beat | Size | Source |
| --- | --- | --- | --- |
| `s01-readme-top.png` | 2 | 1920×2920 | GitHub README, signed out, 1280 viewport · DPR 2 |
| `s02-console-idle.png` | 3 | 2400×12432 | Space console at rest, 1200 viewport · DPR 2 |
| `s03-space-url.png` | 3 | 1920×1080 | Window capture — the only frame showing the Space's own URL |
| `s04-timeline-executing.png` | 5 | 2400×12488 | Space console with a step durably `executing` |
| `s05-explain-plan.png` | 11 | 1920×1080 | Terminal `EXPLAIN` against the Cloud cluster |
| `s07-ci-badges.png` | 13 | 1920×1080 | Crop of the `s01` capture |
| `s08-adr-list.png` | 13 | 1920×1380 | Crop of the `s01` capture |
| `s10-codecov.png` | 13 | 1920×1080 | Codecov's page for the repo, signed out, 1400 viewport · DPR 2, **charts hidden** — see below |

Two are **not** here on purpose. `s09-lambda-console` is served by
[`../../provider-evidence/09.lambda-configuration.png`](../../provider-evidence/09.lambda-configuration.png),
which already states the absence ADR 002 rests on — *Provisioned concurrency (0) — No
configurations* — in AWS's own console, at exactly 1920×1080. `s06-mcp-panel` is the fallback for
Recording #2; that take was shot on 2026-08-11, so the fallback never triggered and the still stays
uncaptured rather than becoming a frame nobody uses.

**`s10` needed the page's own "Hide charts" toggle before it could be framed.** With the chart block
expanded the page is ratio 1.12, and no 16:9 crop of it holds both the coverage figure and the file
table — the first attempt kept the number and lost the table entirely. Hidden, that ~930px of
mostly-empty grey goes away and the page is 1.77, so everything fits: repo, branch, source commit,
`100.00%`, `315 of 315 lines covered`, and `agents`/`api`/`observability` each at 100% with a
`Subtotal` of 315. Captured **signed out** on purpose — `Log in` in the nav and `Viewing as visitor`
beside the repo name show a judge can open the same page, and a signed-out page has no avatar to
mask. It is a Type A capture rather than a window capture because the same figure renders about 1.8×
larger that way, and the frame is on screen for two seconds.

`s01`, `s07` and `s08` are three crops of one capture rather than three separate shots — the same
page, framed three ways, so the badge row and the ADR table cannot drift from the README they were
cut out of.

**`s02` and `s04` are dated photographs of a moving number.** Their KPI tiles read 58 and 59
resolved incidents; the cluster keeps climbing as evidence runs and Lambda ticks are driven against
it. That is the same position [`../../../submission/SUBMISSION.md`](../../../submission/SUBMISSION.md)
takes for `provider-evidence/01`, and it is not a reason to re-shoot.
