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
}


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

    undeclared = _undeclared()

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
        print(f"All declared regions are redacted; {len(REDACTIONS)} screenshot(s) declared.")
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
