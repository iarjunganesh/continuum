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
EVIDENCE = REPO_ROOT / "assets" / "provider-evidence"

# A flat, obviously-synthetic disc rather than a blur. A blur reads as "something was hidden
# here", which invites the question of what; a neutral placeholder reads as "no avatar", which
# is both true and uninteresting. Sampled to sit against the toolbar's near-white background
# without drawing the eye.
PLACEHOLDER = (199, 199, 204)


AVATAR = (1752, 47, 1777, 72)
# Edge's toolbar avatar sits on identical pixels in every 1920x1080 capture, so the box is
# named once rather than repeated per file and drifting.

# The AWS console's account tooltip: "iarjunganesh (504804196134) v" in the top-right nav.
# Only the parenthesised account id is covered — the username is the same public handle as the
# GitHub org and the Hugging Face Space, so hiding it would be theatre. Filled with the
# tooltip's own background colour, sampled from the frame, so the result reads as a tooltip
# that simply shows a username.
AWS_ACCOUNT_ID = (1778, 82, 1878, 101)
AWS_TOOLTIP_BG = (125, 137, 152)

# The CloudWatch Logs *log-events* page renders the same tooltip about 16px further right than the
# Metrics pages do, so the box above lands inside the username and leaves the closing paren showing.
# Measured off the unredacted capture rather than eyeballed: the username's ink run ends at x=1792
# and `(504804196134)` occupies x=1797..1879, inside a tooltip whose background spans y=81..99.
# Two boxes rather than one generous box that would swallow the username on every page — the
# username is deliberately left legible, so a mask wide enough to cover both positions would hide
# something this folder has decided not to hide.
AWS_ACCOUNT_ID_LOGS = (1794, 81, 1881, 100)


@dataclass(frozen=True)
class Region:
    """One rectangle to mask. `circle` draws an ellipse inscribed in it instead."""

    box: tuple[int, int, int, int]  # left, top, right, bottom
    why: str
    circle: bool = False
    fill: tuple[int, int, int] | None = None  # defaults to PLACEHOLDER


# Keyed by filename. Edge renders its toolbar at a fixed position in a 1920x1080 window, so the
# avatar lands on the same pixels in every capture taken that way — verified per file rather
# than assumed, by cropping the region out of each before writing this.
REDACTIONS: dict[str, tuple[Region, ...]] = {
    "03.crdb-cluster-overview-eu-central-1.png": (Region(AVATAR, "signed-in user's profile photograph", circle=True),),
    "04.crdb-metrics-full-page.png": (Region(AVATAR, "signed-in user's profile photograph", circle=True),),
    "05.crdb-sql-activity-fingerprints.png": (Region(AVATAR, "signed-in user's profile photograph", circle=True),),
    "06.crdb-jobs-history.png": (Region(AVATAR, "signed-in user's profile photograph", circle=True),),
    "07.crdb-service-account-mcp.png": (Region(AVATAR, "signed-in user's profile photograph", circle=True),),
    "08.bedrock-invocations-and-latency-table.png": (
        Region(AVATAR, "signed-in user's profile photograph", circle=True),
        Region(AWS_ACCOUNT_ID, "AWS account id in the console's account tooltip", fill=AWS_TOOLTIP_BG),
    ),
    "09.lambda-configuration.png": (
        Region(AVATAR, "signed-in user's profile photograph", circle=True),
        Region(AWS_ACCOUNT_ID, "AWS account id in the console's account tooltip", fill=AWS_TOOLTIP_BG),
    ),
    "10.lambda-metrics-table.png": (
        Region(AVATAR, "signed-in user's profile photograph", circle=True),
        Region(AWS_ACCOUNT_ID, "AWS account id in the console's account tooltip", fill=AWS_TOOLTIP_BG),
    ),
    "11.lambda-log-stream-recovery.png": (
        Region(AVATAR, "signed-in user's profile photograph", circle=True),
        Region(AWS_ACCOUNT_ID_LOGS, "AWS account id in the console's account tooltip", fill=AWS_TOOLTIP_BG),
    ),
}


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
        path = EVIDENCE / name
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

    if check_only:
        if missing:
            print("Unredacted regions found:")
            for m in missing:
                print(f"  {m}")
            print("\nRun: python scripts/redact_evidence.py")
            return 1
        print("All declared regions are redacted.")
        return 0

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
