"""
Mask personal or account-identifying pixels in judge-facing screenshots (`make redact-evidence`).

These files are evidence. Editing them is therefore something to do rarely, narrowly, and
visibly — which is why the redactions live here as data rather than being applied by hand in an
image editor and forgotten. Every region below states what it covers and why, the script is
idempotent, and `assets/provider-evidence/README.md` declares that it ran.

What this is allowed to touch:

  - A person's face or photograph. The browser toolbar in the CockroachDB captures carries the
    signed-in user's profile picture, which is a photograph of a real human being in material
    that goes to judges. Nothing in the evidence depends on it.
  - An AWS account id. `submission/SUBMISSION.md` bars account ids from judge-facing frames, and
    the Lambda console prints the function ARN — which contains one — at the top of the page.

What this must NEVER touch, however tempting:

  - Any metric, count, axis, legend, timestamp, status, query text or identifier that the
    surrounding prose cites. Masking a number to make it agree with a document would turn
    evidence into decoration, and the whole point of this folder is that these are screens the
    project cannot fake.
  - The CockroachDB cluster id and the MCP service-account id. Those are *identifiers, not
    secrets* — useless without credentials that are not here — and redacting them would weaken
    the corroboration the files exist to provide. That reasoning is recorded in the folder's
    README; if it ever changes, change it there first.

Usage:
    python scripts/redact_evidence.py            # apply, report what changed
    python scripts/redact_evidence.py --check    # exit 1 if any region is still unredacted
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"

# Every family of judge-facing screenshots, so a capture cannot be added without a decision
# about it being recorded. `provider-evidence/` was the only one when this script was written;
# `chaos-run/*/screenshots/` arrived later carrying the *same* browser chrome, and nothing
# mechanical noticed. A declaration check beats remembering.
#
# `demo-video/` and its `statics/` are included for the same reason even though neither holds a
# PNG yet: `statics/` is where the still frames cut into the demo video's beats will live, and a
# frame that appears on screen in a submitted video is as judge-facing as anything in
# `provider-evidence/`. Covering it now means the first capture dropped there fails `--check`
# until someone decides about it, rather than shipping because nobody looked.
SCREENSHOT_GLOBS = (
    "provider-evidence/*.png",
    "chaos-run/*/screenshots/*.png",
    "demo-video/*.png",
    "demo-video/statics/*.png",
)

# A flat, obviously-synthetic disc rather than a blur. A blur reads as "something was hidden
# here", which invites the question of what; a neutral placeholder reads as "no avatar", which
# is both true and uninteresting. Sampled to sit against the toolbar's near-white background
# without drawing the eye.
PLACEHOLDER = (199, 199, 204)


AVATAR = (1752, 47, 1777, 72)
# Edge's toolbar avatar sits on identical pixels in every 1920x1080 capture, so the box is
# named once rather than repeated per file and drifting.

# ...except in the OBS recordings, where it does not. Measured off `mcp-query-take.mp4` rather
# than assumed from AVATAR: the disc there spans x=1755..1778, y=48..71 — three pixels right of
# where the DevTools captures put it, because OBS records the desktop rather than the viewport.
# Reusing AVATAR would leave column 1778 showing, which is the same one-pixel crescent this
# file's history already records once. The box below inscribes an ellipse with a pixel of margin
# on every side.
AVATAR_TAKE = (1754, 47, 1780, 73)

# The AWS console's account tooltip: "iarjunganesh (<account-id>) v" in the top-right nav.
# Only the parenthesised account id is covered — the username is the same public handle as the
# GitHub org and the Hugging Face Space, so hiding it would be theatre. Filled with the
# tooltip's own background colour, sampled from the frame, so the result reads as a tooltip
# that simply shows a username.
AWS_ACCOUNT_ID = (1778, 82, 1878, 101)
AWS_TOOLTIP_BG = (125, 137, 152)

# The CloudWatch Logs *log-events* page renders the same tooltip about 16px further right than the
# Metrics pages do, so the box above lands inside the username and leaves the closing paren showing.
# Measured off the unredacted capture rather than eyeballed: the username's ink run ends at x=1792
# and `(<account-id>)` occupies x=1797..1879, inside a tooltip whose background spans y=81..99.
# Two boxes rather than one generous box that would swallow the username on every page — the
# username is deliberately left legible, so a mask wide enough to cover both positions would hide
# something this folder has decided not to hide.
AWS_ACCOUNT_ID_LOGS = (1794, 81, 1881, 100)

# And the Logs *search* page ("All events") shifts it again. Measured off
# `0b99a950_09-…png` rather than reused: on that layout `(<account-id>)` runs x=1810..1884
# inside a tooltip spanning y=81..97, so the box above would stop three pixels short and leave
# the closing parenthesis showing — the exact failure this file's history warns about. The
# username's ink ends at x=1806, so the left edge sits at 1808 and keeps it legible.
AWS_ACCOUNT_ID_LOGS_SEARCH = (1808, 79, 1886, 99)


@dataclass(frozen=True)
class Region:
    """One rectangle to mask. `circle` draws an ellipse inscribed in it instead."""

    box: tuple[int, int, int, int]  # left, top, right, bottom
    why: str
    circle: bool = False
    fill: tuple[int, int, int] | None = None  # defaults to PLACEHOLDER


PHOTO = "signed-in user's profile photograph"
ACCOUNT = "AWS account id in the console's account tooltip"

# Keyed by path relative to `assets/`. Edge renders its toolbar at a fixed position in a
# 1920x1080 window, so the avatar lands on the same pixels in every capture taken that way —
# verified per file rather than assumed, by measuring the region out of each before writing
# this. On the 2026-08-09 chaos captures the photograph's widest row spans x=1753..1776, which
# the inscribed ellipse of AVATAR covers exactly.
#
# A file with an EMPTY tuple is declared and deliberately unmasked. That is not the same as an
# undeclared file: it records that someone looked. Terminal captures carry no browser chrome and
# therefore no face and no account id.
REDACTIONS: dict[str, tuple[Region, ...]] = {
    # --- provider-evidence -------------------------------------------------
    # Full-page captures (1920x2728 and 1920x5412), not window screenshots, so they carry no
    # browser chrome: no avatar, no account tooltip. Verified by measuring the avatar row, not
    # assumed from the filename. Declared so the set is complete.
    "provider-evidence/00.space-first-paint.png": (),
    "provider-evidence/01.space-console-full-page.png": (),
    "provider-evidence/03.crdb-cluster-overview-eu-central-1.png": (Region(AVATAR, PHOTO, circle=True),),
    "provider-evidence/04.crdb-metrics-full-page.png": (Region(AVATAR, PHOTO, circle=True),),
    "provider-evidence/05.crdb-sql-activity-fingerprints.png": (Region(AVATAR, PHOTO, circle=True),),
    "provider-evidence/06.crdb-jobs-history.png": (Region(AVATAR, PHOTO, circle=True),),
    "provider-evidence/07.crdb-service-account-mcp.png": (Region(AVATAR, PHOTO, circle=True),),
    "provider-evidence/08.bedrock-invocations-and-latency-table.png": (
        Region(AVATAR, PHOTO, circle=True),
        Region(AWS_ACCOUNT_ID, ACCOUNT, fill=AWS_TOOLTIP_BG),
    ),
    "provider-evidence/09.lambda-configuration.png": (
        Region(AVATAR, PHOTO, circle=True),
        Region(AWS_ACCOUNT_ID, ACCOUNT, fill=AWS_TOOLTIP_BG),
    ),
    "provider-evidence/10.lambda-metrics-table.png": (
        Region(AVATAR, PHOTO, circle=True),
        Region(AWS_ACCOUNT_ID, ACCOUNT, fill=AWS_TOOLTIP_BG),
    ),
    "provider-evidence/11.lambda-log-stream-recovery.png": (
        Region(AVATAR, PHOTO, circle=True),
        Region(AWS_ACCOUNT_ID_LOGS, ACCOUNT, fill=AWS_TOOLTIP_BG),
    ),
    # --- chaos-run: the local process kill, 2026-08-09 ----------------------
    "chaos-run/local-a2bb201d/screenshots/a2bb201d_00-space-console-at-rest.png": (Region(AVATAR, PHOTO, circle=True),),
    "chaos-run/local-a2bb201d/screenshots/a2bb201d_01-space-console-step-in-flight.png": (
        Region(AVATAR, PHOTO, circle=True),
    ),
    # Terminal capture — no browser chrome, so no face and no account id.
    "chaos-run/local-a2bb201d/screenshots/a2bb201d_02-terminal-kill-pause-and-cold-resume.png": (),
    "chaos-run/local-a2bb201d/screenshots/a2bb201d_03-crdb-console-step-frozen-executing.png": (
        Region(AVATAR, PHOTO, circle=True),
    ),
    "chaos-run/local-a2bb201d/screenshots/a2bb201d_05-space-console-resumed-and-resolved.png": (
        Region(AVATAR, PHOTO, circle=True),
    ),
    "chaos-run/local-a2bb201d/screenshots/a2bb201d_06-crdb-console-executing-then-executed.png": (
        Region(AVATAR, PHOTO, circle=True),
    ),
    "chaos-run/local-a2bb201d/screenshots/a2bb201d_08-space-card-provenance-badges.png": (
        Region(AVATAR, PHOTO, circle=True),
    ),
    # --- chaos-run: AWS delivers the kill, 2026-08-09 -----------------------
    "chaos-run/lambda-0b99a950/screenshots/0b99a950_01-space-console-step-in-flight.png": (
        Region(AVATAR, PHOTO, circle=True),
    ),
    "chaos-run/lambda-0b99a950/screenshots/0b99a950_02-terminal-aws-kill-and-cold-resume.png": (),
    "chaos-run/lambda-0b99a950/screenshots/0b99a950_03-crdb-console-step-frozen-executing-runtime-lambda.png": (
        Region(AVATAR, PHOTO, circle=True),
    ),
    "chaos-run/lambda-0b99a950/screenshots/0b99a950_05-space-console-resumed-resolved-with-lambda-badge.png": (
        Region(AVATAR, PHOTO, circle=True),
    ),
    "chaos-run/lambda-0b99a950/screenshots/0b99a950_06-crdb-console-executing-then-executed-runtime-lambda.png": (
        Region(AVATAR, PHOTO, circle=True),
    ),
    "chaos-run/lambda-0b99a950/screenshots/0b99a950_07-space-mcp-answering-live.png": (
        Region(AVATAR, PHOTO, circle=True),
    ),
    # The only chaos frame from an AWS console, so the only one carrying an account id.
    "chaos-run/lambda-0b99a950/screenshots/0b99a950_09-cloudwatch-timeout-then-cold-recovery-read.png": (
        Region(AVATAR, PHOTO, circle=True),
        Region(AWS_ACCOUNT_ID_LOGS_SEARCH, ACCOUNT, fill=AWS_TOOLTIP_BG),
    ),
    # --- demo-video stills, cut into the video's beats, 2026-08-11 ----------
    # s02 and s04 are DevTools full-page captures (2400px wide, DPR 2) taken with the device
    # toolbar on, so they carry no browser chrome: no Edge toolbar, no avatar, no account id.
    # The Hugging Face badge in the corner is HF's own logo, not a photograph.
    "demo-video/statics/s02-console-idle.png": (),
    "demo-video/statics/s04-timeline-executing.png": (),
    # s03 is the one window capture in the set — it exists to show the Space's real URL in the
    # address bar, which means it also carries the Edge toolbar and the signed-in avatar.
    # Measured off this file rather than assumed: the photograph's widest row spans x=1755..1774
    # and it occupies y=48..71, which AVATAR's inscribed ellipse covers with margin on all sides.
    "demo-video/statics/s03-space-url.png": (Region(AVATAR, PHOTO, circle=True),),
    # Codecov's own page, corroborating the 100% the beat-13 caption claims. A full-page DevTools
    # capture, so it carries no browser chrome and no avatar — and it was taken signed *out*
    # ("Log in" / "Start Free Trial" in the nav, "Viewing as visitor" beside the repo name), which
    # is worth more than a signed-in view: it demonstrates a judge can open the same page. Nothing
    # here may be masked. The repo name, branch, source commit and every coverage figure are the
    # entire point of the frame, and the account handle is the same public one as the GitHub org.
    "demo-video/statics/s10-codecov.png": (),
    # s01/s07/s08 are crops out of one signed-out full-page capture of the GitHub repo
    # (1280 viewport, DPR 2). Signed out, so the header carries "Sign in / Sign up" rather than an
    # avatar — and every crop starts well below the header regardless. No chrome, nothing to mask.
    "demo-video/statics/s01-readme-top.png": (),
    "demo-video/statics/s07-ci-badges.png": (),
    "demo-video/statics/s08-adr-list.png": (),
    # s05 is a terminal capture — no browser chrome, so no avatar and no account id. The DSN never
    # reaches the screen: the runner reads it from the environment and prints only the query plan.
    "demo-video/statics/s05-explain-plan.png": (),
}


# The demo video's own footage. This exists because the screenshot gate above did not catch it:
# `mcp-query-take.mp4` shipped with the signed-in user's photograph in the browser toolbar of
# every one of its 315 frames, and nothing complained, because `SCREENSHOT_GLOBS` walks PNGs.
# A frame that appears in a submitted video is exactly as judge-facing as one in
# `provider-evidence/` — more so, since the video is the thing a judge watches first and the
# only artifact here that cannot be quietly re-uploaded after someone notices.
#
# Same rules as above: an empty tuple means someone looked and it needs nothing.
VIDEO_GLOBS = ("demo-video/*.mp4", "demo-video/beats/*.mp4")

VIDEO_REDACTIONS: dict[str, tuple[Region, ...]] = {
    "demo-video/mcp-query-take.mp4": (Region(AVATAR_TAKE, PHOTO, circle=True),),
    # Two PowerShell panes and nothing else — no browser chrome, so no avatar. The AWS account id
    # would have appeared had the `--via-lambda` leg hit AccessDenied on camera; it did not, and
    # the frames were swept for it before this was declared.
    "demo-video/kill-recover-take.mp4": (),
    # Rendered from the statics, which are declared above and already masked.
    "demo-video/beats/beat02-readme.mp4": (),
    "demo-video/beats/beat03-console.mp4": (),
    "demo-video/beats/beat13-adr.mp4": (),
}

# Frames sampled per video when checking. Three is enough because these regions are browser
# chrome: it does not appear partway through, so a mask that holds at the start, middle and end
# holds throughout. Sampling every frame would make `--check` cost minutes for no more certainty.
VIDEO_SAMPLES = (0.1, 0.5, 0.9)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise SystemExit("ffmpeg is not on PATH — needed to check the demo video's frames")
    return exe


def _duration(path: Path) -> float:
    probe = shutil.which("ffprobe")
    if probe is None:
        raise SystemExit("ffprobe is not on PATH — needed to sample the demo video's frames")
    out = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def _frame_at(path: Path, seconds: float) -> Image.Image:
    out = subprocess.run(
        [
            _ffmpeg(),
            "-v",
            "error",
            "-ss",
            f"{seconds:.3f}",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ],
        capture_output=True,
        check=True,
    )
    return Image.open(io.BytesIO(out.stdout)).convert("RGB")


def _mask_video(path: Path, regions: tuple[Region, ...]) -> None:
    """Composite the placeholder over every frame, then replace the file.

    The mask is drawn once as an RGBA overlay and burned in by ffmpeg rather than frame by frame
    in Pillow: one re-encode instead of a decode/encode round trip per frame, and the result is
    bit-identical across runs.
    """
    probe = _frame_at(path, 0.0)
    overlay = Image.new("RGBA", probe.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for region in regions:
        fill = (*(region.fill or PLACEHOLDER), 255)
        if region.circle:
            draw.ellipse(region.box, fill=fill)
        else:
            draw.rectangle(region.box, fill=fill)

    with tempfile.TemporaryDirectory() as tmp:
        mask = Path(tmp) / "mask.png"
        overlay.save(mask)
        dest = Path(tmp) / path.name
        subprocess.run(
            [
                _ffmpeg(),
                "-y",
                "-v",
                "error",
                "-i",
                str(path),
                "-i",
                str(mask),
                "-filter_complex",
                "[0][1]overlay=0:0",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "16",
                "-pix_fmt",
                "yuv420p",
                str(dest),
            ],
            check=True,
        )
        shutil.copyfile(dest, path)


def _is_masked_in_video(im: Image.Image, region: Region, tolerance: int = 6) -> bool:
    """Same question as `_is_flat`, asked of a frame that has been through H.264.

    The exact-equality test `_is_flat` uses cannot work here: yuv420p subsamples chroma, so a
    disc drawn as (199, 199, 204) decodes as (199, 198, 203) and an equality check would report
    the mask missing on a video that is correctly masked — which would re-encode the file on
    every run, stacking a generation of loss each time. Tolerance is deliberately tight: 6 is
    far below the distance to any photograph, so this still fails loudly on an unmasked frame.
    """
    patch = im.crop(region.box).convert("RGB")
    colours = patch.getcolors(maxcolors=1 << 16)
    if colours is None:
        return False
    want = region.fill or PLACEHOLDER
    near = sum(
        count for count, colour in colours if max(abs(a - b) for a, b in zip(colour, want, strict=True)) <= tolerance
    )
    total = sum(count for count, _ in colours)
    # An inscribed ellipse leaves the box's corners untouched, so the fill covers ~pi/4 of it.
    return near / total > 0.6 if region.circle else near / total > 0.98


def _undeclared_videos() -> list[str]:
    found: set[str] = set()
    for pattern in VIDEO_GLOBS:
        for path in ASSETS.glob(pattern):
            found.add(path.relative_to(ASSETS).as_posix())
    return sorted(found - set(VIDEO_REDACTIONS))


def _undeclared() -> list[str]:
    """Judge-facing screenshots with no entry above.

    The point of the whole file is that masking is a recorded decision. A capture nobody has
    declared is a capture nobody has looked at — which is how a face or an account id ships.
    """
    found: set[str] = set()
    for pattern in SCREENSHOT_GLOBS:
        for path in ASSETS.glob(pattern):
            found.add(path.relative_to(ASSETS).as_posix())
    return sorted(found - set(REDACTIONS))


def _is_flat(im: Image.Image, region: Region) -> bool:
    """Has this region already been masked? True when it is a single solid colour.

    Cheap, and good enough: a photograph is never one colour, and the placeholder always is.
    This is what makes the script idempotent and `--check` meaningful.
    """
    patch = im.crop(region.box).convert("RGB")
    colours = patch.getcolors(maxcolors=1 << 16)
    if colours is None:  # more distinct colours than the cap — definitely not flat
        return False
    want = region.fill or PLACEHOLDER
    if region.circle:
        # An inscribed ellipse leaves the four corners untouched, so expect the fill colour
        # to dominate rather than to be alone.
        total = sum(count for count, _ in colours)
        top = max(count for count, _ in colours)
        return top / total > 0.6 and any(colour == want for _, colour in colours)
    return len(colours) == 1 and colours[0][1] == want


def apply(check_only: bool) -> int:
    missing: list[str] = []
    changed: list[str] = []

    for name, regions in REDACTIONS.items():
        path = ASSETS / name
        if not regions:
            # Declared as deliberately unmasked. Reported so the set stays visible.
            if path.exists() and not check_only:
                print(f"  [none] {name} — declared, nothing to mask")
            continue
        if not path.exists():
            # Not a failure: the evidence set changes as frames are re-captured or dropped,
            # and a stale entry here should not break a build.
            print(f"  [skip] {name} — not present")
            continue

        im = Image.open(path).convert("RGB")
        draw = ImageDraw.Draw(im)
        touched = False
        for region in regions:
            if _is_flat(im, region):
                continue
            if check_only:
                missing.append(f"{name}: {region.why} at {region.box}")
                continue
            fill = region.fill or PLACEHOLDER
            if region.circle:
                draw.ellipse(region.box, fill=fill)
            else:
                draw.rectangle(region.box, fill=fill)
            touched = True

        if touched:
            im.save(path)
            changed.append(name)
            for region in regions:
                print(f"  [mask] {name} — {region.why}")
        elif not check_only:
            print(f"  [ok  ] {name} — already redacted")

    for name, regions in VIDEO_REDACTIONS.items():
        path = ASSETS / name
        if not path.exists():
            print(f"  [skip] {name} — not present")
            continue
        if not regions:
            if not check_only:
                print(f"  [none] {name} — declared, nothing to mask")
            continue

        duration = _duration(path)
        unmasked = [
            region
            for region in regions
            for at in VIDEO_SAMPLES
            if not _is_masked_in_video(_frame_at(path, duration * at), region)
        ]
        if not unmasked:
            if not check_only:
                print(f"  [ok  ] {name} — already redacted")
            continue
        if check_only:
            for region in dict.fromkeys(unmasked):
                missing.append(f"{name}: {region.why} at {region.box}")
            continue
        _mask_video(path, regions)
        changed.append(name)
        for region in regions:
            print(f"  [mask] {name} — {region.why}")

    undeclared = _undeclared() + _undeclared_videos()

    if check_only:
        if missing:
            print("Unredacted regions found:")
            for m in missing:
                print(f"  {m}")
        if undeclared:
            print("Judge-facing screenshots with no declaration:")
            for u in undeclared:
                print(f"  {u}")
            print("\nAdd each to REDACTIONS — an empty tuple if it genuinely needs no mask.")
        if missing or undeclared:
            print("\nRun: python scripts/redact_evidence.py")
            return 1
        print(
            f"All declared regions are redacted; {len(REDACTIONS)} screenshot(s) "
            f"and {len(VIDEO_REDACTIONS)} video(s) declared."
        )
        return 0

    if undeclared:
        # Not fatal here — applying is the fixing step, and refusing to fix what it *can* fix
        # would be unhelpful. `--check` is where this fails a build.
        print("\nWARNING - undeclared judge-facing screenshots:")
        for u in undeclared:
            print(f"  {u}")

    print(f"\n{len(changed)} file(s) modified.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="exit 1 if anything is unredacted")
    args = ap.parse_args()
    print("Continuum - evidence redaction\n")
    return apply(args.check)


if __name__ == "__main__":
    raise SystemExit(main())
