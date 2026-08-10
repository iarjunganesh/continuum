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

# Devpost's project-description field is capped at 50,000 characters and truncates silently on
# paste — you find out by discovering the tail of your submission is missing, which is exactly the
# kind of thing nobody re-reads after pasting. The mirror is *longer* than README.md by
# construction (every relative link becomes an absolute github.com URL, ~4.6k of pure overhead),
# so it can cross the line while the README looks comfortable. Gated here rather than remembered.
MIRROR_MAX_CHARS = 50_000
# Leave room for a paragraph of README growth before this becomes urgent, so the failure arrives
# during ordinary work rather than on deadline day.
MIRROR_WARN_CHARS = 48_500
BLOB = f"https://github.com/{REPO}/blob/{BRANCH}/"
TREE = f"https://github.com/{REPO}/tree/{BRANCH}/"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "README.md"
TARGET = ROOT / "submission" / "DEVPOST_README.md"

# Rendered by GitHub from raw bytes, so they need raw.githubusercontent.com rather than /blob/.
IMAGE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"}

# Sections that earn their place in the repository's README and not in a 50,000-character Devpost
# paste. This is the *only* sanctioned way the two documents differ in content, and it is
# deliberately narrow: a section qualifies solely because a Devpost reader gets the same thing
# better somewhere else, never because it was long and the budget was tight. Each carries a
# replacement line so the paste points at what it dropped rather than silently lacking it —
# an omission a reader can see is a different thing from a gap.
#
# `Project Structure` is a 6.5k-character file tree. GitHub renders the live directory listing
# natively, one click from every repo link in the paste, and it never goes stale the way a
# transcribed tree does. It stays in README.md in full, where `check_drift.py` enforces it against
# the real repo.
DEVPOST_ONLY_OMIT = {
    "## Project Structure": (
        "## Project Structure\n\n"
        "Omitted from this paste for length — GitHub renders the live tree, which cannot go stale:\n"
        f"**[browse the repository]({TREE})**. The annotated version, checked against the real repo\n"
        f"on every commit, is in [`README.md`]({BLOB}README.md#project-structure).\n"
    ),
}

# Every character here is spent against the 50,000-char paste budget, so this says the minimum
# that stops someone hand-editing the file. The full rationale lives in the module docstring and
# in CLAUDE.md, where it costs nothing.
HEADER_NOTE = f"""<!--
  GENERATED from README.md — DO NOT HAND-EDIT. Regenerate:
      python scripts/build_devpost_readme.py         (--check verifies, exit 1 if stale)
  Paste-safe: links absolutised, Space frontmatter stripped, repo-only sections replaced.
  Source: https://github.com/{REPO}/blob/{BRANCH}/README.md
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


def _apply_omissions(text: str) -> str:
    """Swap each DEVPOST_ONLY_OMIT section for its replacement pointer.

    A section runs from its `## ` heading to the next `## ` heading (or EOF), so the trailing
    `---` rule that separates it from the next section goes with it. Missing headings are a hard
    error rather than a silent no-op: renaming a section in README.md must not quietly restore
    6.5k characters to a length-capped file.
    """
    for heading, replacement in DEVPOST_ONLY_OMIT.items():
        start = text.find(f"\n{heading}\n")
        if start == -1:
            raise SystemExit(
                f"build_devpost_readme: DEVPOST_ONLY_OMIT names {heading!r}, which README.md no "
                f"longer contains. Update the heading here, or drop the entry if the section went."
            )
        start += 1
        nxt = text.find("\n## ", start + 1)
        end = len(text) if nxt == -1 else nxt + 1
        text = text[:start] + replacement + "\n---\n\n" + text[end:]
    return text


def build() -> str:
    body = _apply_omissions(_rewrite(_strip_frontmatter(SOURCE.read_text(encoding="utf-8"))))
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

    size = len(generated)
    if size > MIRROR_MAX_CHARS:
        print(
            f"{TARGET.relative_to(ROOT)} is {size:,} chars — {size - MIRROR_MAX_CHARS:,} over "
            f"Devpost's {MIRROR_MAX_CHARS:,}-character limit. Devpost truncates silently, so this "
            f"is a hard failure. Trim README.md, or extend DEVPOST_ONLY_OMIT for a section that "
            f"earns its place in the repo but not in the paste.",
            file=sys.stderr,
        )
        return 1
    if size > MIRROR_WARN_CHARS:
        print(
            f"warning: {TARGET.relative_to(ROOT)} is {size:,} chars, within "
            f"{MIRROR_MAX_CHARS - size:,} of Devpost's {MIRROR_MAX_CHARS:,} limit",
            file=sys.stderr,
        )

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
