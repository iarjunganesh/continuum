"""
Turn the provider-evidence captures into OBS-ready 1920x1080 sources.

OBS wants a 1080p canvas, but browser captures do not arrive that way: some are
a little short of 1080, and full-page captures are several thousand pixels tall.
The naive fix — scale everything to fit — is the one thing not to do here. These
are evidence images whose whole value is that small text (a cluster region, a
statement fingerprint, a step status) stays legible. Squashing a 4564px page into
1080 makes it unreadable, and re-encoding it as a still throws away the detail
permanently.

So the rule this script follows is: **never downscale a still.**

    height == 1080   copy through untouched
    height <  1080   pad by replicating the last row (the bottom of these pages
                     is empty background, so it is invisible — unlike letterbox
                     bars, which read as a black stripe mid-scene)
    height >  1080   do NOT make a still. Emit a 1080p pan video instead, so the
                     page is read at native scale over time rather than shrunk.

Tall pages also tend to carry a wide dead margin — the Space capture is 1920px
wide but its content column is only ~1116px, so 40% of every frame would be
blank. Those are cropped to the content and scaled up to fill the frame, which
is a legibility gain, not a loss: upscaling a crisp capture is far kinder to
small text than downscaling it.

Outputs land in `assets/provider-evidence/1080p/`, alongside a manifest of what
was done to each file. The originals are never modified — they stay the evidence
of record; this directory is derived, and regenerating it is cheap.

Usage:
    python scripts/build_obs_assets.py
    python scripts/build_obs_assets.py --pan-speed 220      # slower, easier to read
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "assets" / "provider-evidence"
DST = SRC / "1080p"
W, H = 1920, 1080
HOLD = 1.5  # seconds held at top and bottom, so a cut never lands mid-motion


def content_columns(im: Image.Image, skip_top: int = 200) -> tuple[int, int]:
    """Horizontal extent of real content, ignoring a full-width header bar."""
    a = np.asarray(im.convert("RGB"))[skip_top : im.height - 20]
    nonwhite = (a.std(axis=2) > 3) | (a.mean(axis=2) < 250)
    cols = np.where(nonwhite.sum(axis=0) > 20)[0]
    return (int(cols.min()), int(cols.max())) if len(cols) else (0, im.width - 1)


def pad_to_1080(im: Image.Image) -> Image.Image:
    out = Image.new("RGB", (W, H))
    out.paste(im.convert("RGB"), (0, 0))
    last = im.convert("RGB").crop((0, im.height - 1, im.width, im.height))
    for y in range(im.height, H):
        out.paste(last, (0, y))
    return out


def make_pan(src: Path, out: Path, speed_px_s: float) -> dict:
    """Crop dead margin, scale the content to fill 1920 wide, pan top→bottom."""
    im = Image.open(src)
    x0, x1 = content_columns(im)
    pad = 16
    x0, x1 = max(0, x0 - pad), min(im.width - 1, x1 + pad)
    cropped = im.convert("RGB").crop((x0, 0, x1 + 1, im.height))
    scale = W / cropped.width
    scaled = cropped.resize((W, round(cropped.height * scale)), Image.LANCZOS)

    # Duration must come from the distance actually travelled *after* upscaling,
    # not from the source height: an upscale multiplies the travel, and deriving
    # the time from the original made the pan scroll far too fast to read.
    travel = max(0, scaled.height - H)
    pan_seconds = max(4.0, round(travel / speed_px_s, 1))

    tmp = out.with_suffix(".src.png")
    scaled.save(tmp)
    total = HOLD * 2 + pan_seconds
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-loop",
                "1",
                "-i",
                str(tmp),
                "-vf",
                f"crop={W}:{H}:0:'(ih-{H})*clip((t-{HOLD})/{pan_seconds}\\,0\\,1)',format=yuv420p",
                "-t",
                f"{total}",
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-crf",
                "16",
                "-preset",
                "slow",
                "-movflags",
                "+faststart",
                str(out),
            ],
            check=True,
        )
    finally:
        tmp.unlink(missing_ok=True)

    return {
        "kind": "pan video",
        "source_size": f"{im.width}x{im.height}",
        "cropped_to": f"{cropped.width}x{cropped.height} (x{x0}-{x1})",
        "upscaled": f"{scale:.2f}x",
        "travel_px": travel,
        "speed_px_s": speed_px_s,
        "duration_s": round(total, 1),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--pan-speed",
        type=float,
        default=300.0,
        help="pan speed in pixels/second at 1080p; ~300 is readable, higher scrolls past the text",
    )
    args = p.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH — needed for the pan videos")

    DST.mkdir(parents=True, exist_ok=True)
    for stale in DST.iterdir():
        if stale.is_file():
            stale.unlink()

    manifest: dict[str, dict] = {}
    for f in sorted(SRC.glob("*.png")):
        im = Image.open(f)
        w, h = im.size
        if h == H and w == W:
            shutil.copy2(f, DST / f.name)
            manifest[f.name] = {"kind": "still", "note": "already 1080p, copied untouched"}
        elif h < H and w == W:
            pad_to_1080(im).save(DST / f.name)
            manifest[f.name] = {"kind": "still", "note": f"padded +{H - h}px, edge-replicated"}
        else:
            out = DST / f"{f.stem}.pan.mp4"
            manifest[f.name] = make_pan(f, out, args.pan_speed)
            manifest[f.name]["output"] = out.name

    (DST / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"{'source':<46} result")
    for name, info in manifest.items():
        detail = info.get("note") or f"{info['output']} — {info['duration_s']}s, upscaled {info['upscaled']}"
        print(f"{name:<46} {detail}")

    bad = [q.name for q in DST.glob("*.png") if Image.open(q).size != (W, H)]
    print(f"\nevery still exactly {W}x{H}: {not bad} {bad or ''}")


if __name__ == "__main__":
    main()
