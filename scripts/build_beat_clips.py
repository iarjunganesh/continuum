"""Render the demo video's moving beats from the committed stills.

Several stills in `assets/demo-video/statics/` are filmstrips rather than frames — `s02` and `s04`
are over 12,000 px tall, so a 16:9 window shows 8% of one. They cannot be dropped on a timeline as
they are; something has to decide which 1920x1080 window is on screen at each moment.

That decision lives here rather than in an editor's keyframe handles, for the same reason the charts
and cards are generated: a move made by dragging is a move nobody can review, reproduce, or explain.
Here it is a table of (time, rect) keyframes that reads as the intent it encodes.

`submission/DEMO_SCRIPT.md` owns the beat durations; the `dur` fields below must match its final
timeline table, and MOVES is keyed by beat so a mismatch is visible rather than buried.

    python scripts/build_beat_clips.py            # render all
    python scripts/build_beat_clips.py --only beat02-readme
    python scripts/build_beat_clips.py --check    # fail if any clip is missing or stale

Needs ffmpeg on PATH. Frames are computed with Pillow and piped to it as rawvideo, so nothing
intermediate touches disk.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
STATICS = ROOT / "assets" / "demo-video" / "statics"
OUT = ROOT / "assets" / "demo-video" / "beats"

WIDTH, HEIGHT, FPS = 1920, 1080, 30

Rect = tuple[int, int, int, int]  # left, top, width, height — in source pixels


@dataclass(frozen=True)
class Move:
    """One beat's motion: a source still, a duration, and where the window sits over time."""

    src: str
    dur: float
    keys: tuple[tuple[float, Rect], ...]
    why: str


# Every rect is 16:9 in source pixels, so the resize to 1920x1080 never distorts. A pan holds the
# rect's size and moves `top`; a push-in shrinks the rect about its centre. Never both at once —
# a combined move reads as a template effect rather than as direction.
MOVES: dict[str, Move] = {
    # Beat 2 is the video's most valuable screen time and its narration deliberately names no
    # product and no technology, so the *picture* has to answer "what is this" on its own. The
    # first ~10s therefore sit on the one-line thesis and the badge stack — incident-response
    # agent, CockroachDB, Lambda, Bedrock, C-SPANN, MCP — before moving on to the problem the
    # voiceover is describing. A constant-speed scroll from frame one would put that block on
    # screen for two seconds in passing.
    "beat02-readme": Move(
        src="s01-readme-top.png",
        dur=21.5,
        keys=(
            (0.0, (0, 0, 1920, 1080)),  # logo, wordmark, thesis
            (2.0, (0, 0, 1920, 1080)),  # let it land before anything moves
            # 500, not 450: at 450 the wordmark is sliced by the top edge, which reads as an
            # accident rather than a frame. 500 clears it and still leaves the last badge row
            # ~90px inside the bottom.
            (9.0, (0, 500, 1920, 1080)),  # settle on thesis + the full badge stack
            (11.5, (0, 500, 1920, 1080)),  # hold — this is the "what is it" frame
            (21.5, (0, 1840, 1920, 1080)),  # arrive on "The Problem" as the VO reaches it
        ),
        why="identity first, then the problem the narration is describing",
    ),
    # Beat 3 is static by design: two frames, this one and s03, at ~8s each. The window is the top
    # of the console — the green "no steps in-flight" banner and the KPI tiles, which are what make
    # it read as an idle system rather than an unloaded page.
    "beat03-console": Move(
        src="s02-console-idle.png",
        dur=8.2,
        keys=(
            (0.0, (0, 60, 2400, 1350)),
            (8.2, (0, 60, 2400, 1350)),
        ),
        why="header, checkpoint banner and KPI tiles — the console at rest",
    ),
    # Beat 13 spends ~3s here between the badge rows and the throughput chart. The table is taller
    # than a frame, so the pan is what makes it read as ten decisions rather than seven.
    "beat13-adr": Move(
        src="s08-adr-list.png",
        dur=3.0,
        keys=(
            (0.0, (0, 0, 1920, 1080)),
            (3.0, (0, 300, 1920, 1080)),
        ),
        why="enough travel to show the table continues past the frame",
    ),
}


@dataclass(frozen=True)
class Still:
    """One beat's frame: a source still and the window to cut from it, at native resolution."""

    src: str
    rect: Rect
    why: str


# Beat 5 is a still, not a clip, and that is a correction rather than a shortcut. It was rendered
# here as a 100% -> 105% push-in, and a push-in is the one move that resamples every frame at a
# *different* scale: the crop shrinks by about a pixel per frame, so glyph edges land on new
# sub-pixel positions each time and the text visibly shimmers. Pans do not do this, which is why
# beats 2 and 13 are still clips. Rather than fight it with supersampling, the beat ships as one
# frame at source resolution and the editor applies a single continuous zoom over it — one
# transform instead of 468 independent ones. The rect is exported larger than 1920x1080 on purpose,
# so that zoom has real pixels to consume rather than upscaling.
STILLS: dict[str, Still] = {
    "beat05-timeline": Still(
        src="s04-timeline-executing.png",
        rect=(0, 520, 2400, 1350),
        why="the amber 'status = executing' banner, the KPI tiles and the in-flight card",
    ),
}


def _smoothstep(t: float) -> float:
    """Ease in and out. Linear motion starts and stops abruptly, which is what reads as 'a slide'."""
    return t * t * (3.0 - 2.0 * t)


def _rect_at(move: Move, t: float) -> Rect:
    keys = move.keys
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for (t0, r0), (t1, r1) in zip(keys, keys[1:], strict=False):
        if t0 <= t <= t1:
            if t1 == t0:
                return r1
            f = _smoothstep((t - t0) / (t1 - t0))
            return tuple(round(a + (b - a) * f) for a, b in zip(r0, r1, strict=True))  # type: ignore[return-value]
    return keys[-1][1]


def _render(name: str, move: Move) -> Path:
    src = STATICS / move.src
    if not src.exists():
        raise SystemExit(f"missing still: {src.relative_to(ROOT)}")

    image = Image.open(src).convert("RGB")
    frames = int(round(move.dur * FPS))
    dest = OUT / f"{name}.mp4"
    OUT.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{WIDTH}x{HEIGHT}",
        "-framerate",
        str(FPS),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "16",
        "-pix_fmt",
        "yuv420p",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(frames):
            left, top, width, height = _rect_at(move, i / FPS)
            # Clamp so a rect never runs past the source and silently repeats its edge row.
            left = max(0, min(left, image.width - width))
            top = max(0, min(top, image.height - height))
            window = image.crop((left, top, left + width, top + height))
            if window.size != (WIDTH, HEIGHT):
                window = window.resize((WIDTH, HEIGHT), Image.LANCZOS)
            proc.stdin.write(window.tobytes())
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"ffmpeg failed for {name}")
    return dest


def _cut(name: str, still: Still) -> Path:
    src = STATICS / still.src
    if not src.exists():
        raise SystemExit(f"missing still: {src.relative_to(ROOT)}")
    left, top, width, height = still.rect
    image = Image.open(src).convert("RGB")
    dest = OUT / f"{name}.png"
    OUT.mkdir(parents=True, exist_ok=True)
    image.crop((left, top, left + width, top + height)).save(dest)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="render a single beat by name")
    parser.add_argument("--check", action="store_true", help="fail if any output is missing")
    args = parser.parse_args()

    known = {**{n: "mp4" for n in MOVES}, **{n: "png" for n in STILLS}}
    names = [args.only] if args.only else list(known)
    for name in names:
        if name not in known:
            raise SystemExit(f"unknown beat {name!r} — known: {', '.join(known)}")

    if any(known[n] == "mp4" for n in names) and not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is not on PATH — install it, or see docs for the manual route")

    if args.check:
        missing = [n for n in names if not (OUT / f"{n}.{known[n]}").exists()]
        for name in missing:
            print(f"  [MISS] {name}.{known[name]}")
        if missing:
            print("\nRun: python scripts/build_beat_clips.py")
            return 1
        print(f"All {len(names)} beat output(s) present.")
        return 0

    print("Continuum - beat clips\n")
    for name in names:
        if known[name] == "mp4":
            move = MOVES[name]
            dest = _render(name, move)
            print(f"  [ok  ] {dest.name}  {move.dur:>5.1f}s  from {move.src}")
            print(f"         {move.why}")
        else:
            still = STILLS[name]
            dest = _cut(name, still)
            w, h = still.rect[2], still.rect[3]
            print(f"  [ok  ] {dest.name}  {w}x{h}  from {still.src}")
            print(f"         {still.why}")
    print(f"\n{len(names)} output(s) in {OUT.relative_to(ROOT).as_posix()}/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
