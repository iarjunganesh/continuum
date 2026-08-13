# Demo Video

Final cut and its source material. Beat-by-beat script: [`../../submission/DEMO_SCRIPT.md`](../../submission/DEMO_SCRIPT.md).

| File | Use | State |
| --- | --- | --- |
| `continuum.mp4` | The submitted cut | **published 2026-08-12** — https://youtu.be/LwD8__sKqa0. 2:55.7, 1920×1080/30, audio at −14 LUFS. **Not committed**: at 252 MB it exceeds GitHub's 100 MB hard per-file limit, so YouTube is the artifact and this repo carries the sources it was cut from |
| `continuum.srt` | Captions, timed to the measured narration clips | **generated** — `make voiceover` |
| `kill-recover-take.mp4` | Recording #1: beats 6–8 — the kill and the cold resume | **captured 2026-08-11** — 42.0s, 1920×1080/30. Kill at 0:11, 13s hold on the dead terminal, resume JSON at 0:36. One take; the only edit is a splice at 0:06 removing pre-kill idle, across which pane 1 is static |
| `mcp-query-take.mp4` | Recording #2: the live MCP query, beat 12 | **captured 2026-08-11** — 10.5s, 1920×1080/30. Click, spinner, then the answer naming the same incident Recording #1 killed |
| `beats/` | Beats 2, 3 and 13 as rendered clips, plus beat 5 as a single frame the editor zooms | **generated** — `make beat-clips`; see [`beats/README.md`](beats/README.md) |
| `statics/` | Still frames — README top, console, `EXPLAIN` plan, CI badges, ADR list, Codecov | **captured 2026-08-11** — `s01`–`s05`, `s07`, `s08`, `s10`; see [`statics/README.md`](statics/README.md) for the inventory. `s09` is served by `../provider-evidence/09.lambda-configuration.png`; `s06` is the Recording #2 fallback and is captured only if that take is cut. Every PNG is declared in `scripts/redact_evidence.py` — `--check` fails on an undeclared one |

Both takes are **re-encoded at CRF 16, audio stripped**. The raw OBS captures stay out of the repo
(`.takes/`, gitignored): at 16 Mbps CBR they are 120 MB together, and the one that matters was 3.5 MB
under GitHub's 100 MB hard per-file limit. Screen content compresses extremely well — the same frames
at CRF 16 are 1.5 MB total with no visible loss in the terminal text, which is the only thing in
frame that a lower bitrate would hurt. Audio is stripped because both tracks are silent desktop
capture and the cut is scored entirely from `../demo-voiceover/`; a silent track on the timeline is
something to mute by hand and forget.

**Never hand-edit `continuum.srt`.** It is regenerated from
[`scripts/generate_demo_voiceover.py`](../../scripts/generate_demo_voiceover.py), which owns the
narration text; an edit here is destroyed on the next run and, worse, silently desynchronises the
captions from the committed audio.

**Status:** published. `README.md`'s Live Demo table and its `▶ Watch` badge both point at
https://youtu.be/LwD8__sKqa0. The badge is an image URL rather than a claim `check_drift.py` parses, so nothing mechanical
guards it — if the video is ever re-uploaded, that link is the one to change by hand.

## Hard requirements (hackathon rules)

- Under 3 minutes, public on YouTube or Vimeo
- Shows the project functioning on its intended platform
- Shows the CockroachDB memory layer at work — the kill-and-resume beat is non-negotiable
- No third-party trademarks or unlicensed music
