# Beat clips — the video's moving frames

**Generated.** Source: [`../statics/`](../statics/) + [`../../../scripts/build_beat_clips.py`](../../../scripts/build_beat_clips.py).
Regenerate with `make beat-clips` (or `python scripts/build_beat_clips.py` — Windows has no `make`).
Never hand-edit a file here; edit the keyframes or the rect in the script and re-render.

| Output | Beat | Duration | From | Move |
| --- | --- | --- | --- | --- |
| `beat02-readme.mp4` | 2 | 21.5s | `s01-readme-top.png` | hold → settle on the thesis and badges → pan to "The Problem" |
| `beat03-console.mp4` | 3 | 8.2s | `s02-console-idle.png` | static crop |
| `beat05-timeline.png` | 5 | — | `s04-timeline-executing.png` | **none — the editor zooms this one**, see below |
| `beat13-adr.mp4` | 13 | 3.0s | `s08-adr-list.png` | pan down |

Clips are 1920×1080, 30 fps, H.264 — the timeline's format, so they drop in with no conversion and
no scaling. Durations come from the final beat timeline in
[`../../../submission/DEMO_SCRIPT.md`](../../../submission/DEMO_SCRIPT.md); if a beat's length moves
there, move it in the script and re-render, or the audio will drift against the picture.

`beat05-timeline.png` is the exception, and is deliberately **2400×1350 rather than 1920×1080** —
the editor zooms it, so it ships with 25% more pixels than the frame needs and the zoom consumes
real detail instead of upscaling.

## Why beat 5 is a still and the others are clips

Beat 5 was rendered here as a 100% → 105% push-in and **visibly shimmered**. A push-in is the one
move that resamples every frame at a *different scale*: the crop shrinks by about a pixel per frame,
so glyph edges land on new sub-pixel positions each time and small text crawls. Pans do not — the
scale is constant and only the offset moves, which is why beats 2 and 13 are clean.

The fix is not more filtering, it is fewer resamples: ship one frame and let the editor apply a
single continuous zoom across the beat, so the picture is transformed once rather than 468 times.
That gives up the reproducibility argued for below **for this beat only**, which is the right trade
when the alternative is a rendered artifact that looks broken. The rect it is cut from still lives
in the script, so *which* frame is chosen remains reviewable — only the motion moved to the editor.

## Why these are rendered rather than keyframed in the editor

`s02` and `s04` are **filmstrips, not frames** — over 12,000 px tall, so a 16:9 window shows about
8% of one. They cannot be placed on a timeline as they are: something has to choose which
1920×1080 window is on screen at each moment, and if the script doesn't, the editor picks for you.

Doing it here buys three things a drag handle cannot:

- **The move is reviewable.** `(9.0, (0, 500, 1920, 1080))` states where the frame sits and when.
  A keyframe dragged in Clipchamp records nothing about intent and cannot be diffed.
- **It is reproducible.** Re-shoot a still, re-run, and the move is identical. The 100% → 105%
  push-in is exactly 105%, not "about right".
- **`beat02` can hold where holding matters.** Beat 2's narration names no product and no
  technology for twenty seconds, so the picture is what answers *"what is this?"*. The clip settles
  at 0:12–0:15 on the frame carrying the one-line thesis and the whole badge stack, instead of
  scrolling past it in two seconds. That is a deliberate piece of direction, and it lives in the
  keyframe table where someone can argue with it.

`beat03` is static by design — beat 3 is `static ×2` in the timeline. It is still rendered, because
the value there is the locked crop and the exact duration, not motion.

## Not committed to the Hugging Face Space

`.github/workflows/sync-to-hf-space.yml` strips MP4s before pushing to the Hub, which is fine:
nothing the Space renders lives here. These are edit-room source material, not part of the app.
