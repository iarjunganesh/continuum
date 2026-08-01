"""
Generate submission/DEVPOST_README.md — a paste-safe mirror of the root README.md.

Devpost's project-description field has no repo-root context, so every relative link and image
path has to become an absolute github.com / raw.githubusercontent.com URL or it 404s once pasted.
This script does that rewrite mechanically, so the mirror can be *regenerated* rather than
hand-maintained — the two can't drift.

    python scripts/build_devpost_readme.py           # write the mirror
    python scripts/build_devpost_readme.py --check   # verify it's current (CI-friendly, exit 1 if stale)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = "iarjunganesh/continuum"
BRANCH = "main"
BLOB = f"https://github.com/{REPO}/blob/{BRANCH}/"
TREE = f"https://github.com/{REPO}/tree/{BRANCH}/"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "README.md"
TARGET = ROOT / "submission" / "DEVPOST_README.md"

# Rendered by GitHub from raw bytes, so they need raw.githubusercontent.com rather than /blob/.
IMAGE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"}

HEADER_NOTE = f"""<!--
  MAINTAINER NOTE — this block is an HTML comment so the whole file stays paste-safe:
  select all, paste into Devpost, and nothing below renders as meta-commentary.

  This is a Devpost-paste mirror of the root README.md
  (https://github.com/{REPO}/blob/{BRANCH}/README.md).
  Devpost's project-description field has no repo-root context, so every relative link and image
  path below is rewritten to an absolute github.com / raw.githubusercontent.com URL — paste this
  file's content directly into the Devpost form and every link and image still resolves.

  DO NOT HAND-EDIT. Regenerate instead, so the two can never drift:

      python scripts/build_devpost_readme.py

  Verify it is current (exits 1 if stale):

      python scripts/build_devpost_readme.py --check

  The Hugging Face Space frontmatter at the top of README.md is stripped here — it configures the
  Space build and would render as stray text on Devpost.
-->
"""


def _is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "#", "mailto:"))


def _absolute(path: str) -> str:
    """Map a repo-relative path to its absolute GitHub URL."""
    clean = path.split("#")[0]
    if Path(clean).suffix.lower() in IMAGE_SUFFIXES:
        return RAW + path
    # No suffix, or a trailing slash, means a directory listing.
    if path.endswith("/") or not Path(clean).suffix:
        return TREE + path.rstrip("/") + "/"
    return BLOB + path


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + len("\n---\n") :].lstrip("\n")


def _rewrite(text: str) -> str:
    # Badge links first: [![alt](image-url)](target). The generic pattern below can't see these —
    # its [^\]]* label class stops at the inner image's closing bracket, so the outer target is
    # never rewritten and ships as a relative link.
    def badge(match: re.Match[str]) -> str:
        inner, target = match.group(1), match.group(2)
        if _is_external(target):
            return match.group(0)
        return f"[{inner}]({_absolute(target)})"

    text = re.sub(r"\[(!\[[^\]]*\]\([^)\s]+\))\]\(([^)\s]+)\)", badge, text)

    # Markdown links and images: [label](target) / ![alt](target)
    def md(match: re.Match[str]) -> str:
        prefix, label, target = match.group(1), match.group(2), match.group(3)
        if _is_external(target):
            return match.group(0)
        return f"{prefix}[{label}]({_absolute(target)})"

    text = re.sub(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)", md, text)

    # HTML src / srcset / href attributes — the <picture> embeds and the
    # click-to-enlarge <a> wrappers around them. href matters as much as src:
    # miss it and the diagram renders on Devpost but every "click to enlarge"
    # link 404s.
    def attr(match: re.Match[str]) -> str:
        name, target = match.group(1), match.group(2)
        if _is_external(target):
            return match.group(0)
        return f'{name}="{_absolute(target)}"'

    return re.sub(r"\b(src|srcset|href)=\"([^\"]+)\"", attr, text)


def build() -> str:
    body = _rewrite(_strip_frontmatter(SOURCE.read_text(encoding="utf-8")))
    # Keep the H1 first so Devpost's preview leads with the project name, note directly beneath.
    lines = body.split("\n", 1)
    title, rest = (lines[0], lines[1]) if lines[0].startswith("# ") else ("", body)
    if title:
        return f"{title}\n\n{HEADER_NOTE}\n{rest.lstrip(chr(10))}"
    return f"{HEADER_NOTE}\n{body}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the mirror is current")
    args = parser.parse_args()

    generated = build()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != generated:
            print(
                f"{TARGET.relative_to(ROOT)} is stale — run: python scripts/build_devpost_readme.py",
                file=sys.stderr,
            )
            return 1
        print(f"{TARGET.relative_to(ROOT)} is current")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(generated, encoding="utf-8", newline="\n")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(generated.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
