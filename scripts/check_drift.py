"""
Fail the build when a document disagrees with the repo (`make check-drift`).

CLAUDE.md has always asked for a documentation sweep on every change. Asking was
not enough: a release date four days in the future shipped on page one of the
changelog, and a stale test count survived four separate "sweeps" because each
one checked the places someone happened to think of. Every drift caught in this
project so far was found by a human noticing, which does not scale and is not
reliable.

So the sweep is a gate now. Each check below exists because that exact thing
went stale at least once:

  1. Version fields agree (pyproject, api/main.py, CHANGELOG's top release)
  2. No date anywhere is in the future
  3. Stated test counts match what pytest actually collects
  4. Stated ADR count matches docs/adr/
  5. Every relative markdown link resolves
  6. Generated files are current (the Devpost mirror)
  7. The Lambda manifest has not drifted from requirements.txt
  8. README's Project Structure names every real path, and every enumerated
     directory names all of its children
  9. Repo paths written in prose (backticks, not links) resolve — this is how
     references to renumbered evidence frames survived a whole release
 10. README embeds binaries by absolute URL, never relative: README.md is also
     the Hugging Face Space's landing page and the sync strips every binary, so
     a relative PNG renders on GitHub and 404s on the public demo
 11. Docs crediting the generated charts name the run they actually regenerate
     from, recomputed rather than trusted

Every check here has been run against the bug it was written for and watched to
fail. Two of these three did not fire on first write — one regex could not cross
a `.` in a glob — and a gate that has only ever been seen passing is indis-
tinguishable from one that does nothing.

Exit code 0 only when everything agrees, so CI can gate on it.

Usage:
    python scripts/check_drift.py           # report everything, exit 1 on any failure
    python scripts/check_drift.py --quiet   # only failures
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", ".git", "node_modules", "__pycache__", ".mypy_cache", ".aws-sam"}

Failure = tuple[str, str]  # (check name, detail)


def _markdown_files() -> list[Path]:
    return [p for p in REPO_ROOT.rglob("*.md") if not any(part in SKIP_DIRS for part in p.parts)]


def _text_files() -> list[Path]:
    exts = {".md", ".py", ".toml", ".yaml", ".yml", ".example", ".txt", ".json"}
    return [
        p
        for p in REPO_ROOT.rglob("*")
        if p.is_file() and p.suffix in exts and not any(part in SKIP_DIRS for part in p.parts)
    ]


# --------------------------------------------------------------------------
def check_versions() -> list[Failure]:
    """pyproject, api/main.py and the CHANGELOG's newest release must agree."""
    fails: list[Failure] = []
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    canonical = pyproject["project"]["version"]

    api = (REPO_ROOT / "api" / "main.py").read_text(encoding="utf-8")
    m = re.search(r'version\s*=\s*"([^"]+)"', api)
    if not m:
        fails.append(("versions", "could not find app.version in api/main.py"))
    elif m.group(1) != canonical:
        fails.append(("versions", f"api/main.py is {m.group(1)}, pyproject.toml is {canonical}"))

    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M)
    if not released:
        fails.append(("versions", "CHANGELOG.md has no released version heading"))
    elif released[0] != canonical:
        fails.append(("versions", f"CHANGELOG's newest release is {released[0]}, pyproject.toml is {canonical}"))
    return fails


# Dates that are legitimately in the future because they are *deadlines*, not
# claims about work already done. Listed explicitly with a reason: a bare
# "ignore future dates in these files" rule would have let the bad changelog
# date through, since it lived in a file that also contains real deadlines.
KNOWN_FUTURE_DATES: dict[str, str] = {
    "2026-08-03": "CockroachDB trial credits expire",
    "2026-08-18": "hackathon submission deadline",
    "2026-08-19": "judging period opens",
    "2026-09-15": "judging period closes",
    "2026-09-21": "winners announced",
}

# A line may opt out explicitly when it genuinely describes something scheduled.
_ALLOW_MARKER = "drift-allow-future"


def check_no_future_dates() -> list[Failure]:
    """A doc must not describe as done something that has not happened yet.

    This is the check that would have caught `## [0.7.0] — 2026-08-06` at the top
    of the changelog four days before that date existed.

    Future dates are not banned outright — deadlines are legitimately ahead of
    today. They must be *known*, which forces a new one to be justified rather
    than waved through, and keeps this check from becoming noise people ignore.
    """
    today = dt.date.today()
    pattern = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
    fails: list[Failure] = []
    for path in _text_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel == "scripts/check_drift.py":
            continue  # this file names dates in order to reason about them
        for lineno, line in enumerate(text.splitlines(), 1):
            if _ALLOW_MARKER in line:
                continue
            for y, mo, d in pattern.findall(line):
                try:
                    found = dt.date(int(y), int(mo), int(d))
                except ValueError:
                    continue
                if found <= today:
                    continue
                iso = found.isoformat()
                if iso in KNOWN_FUTURE_DATES:
                    continue
                fails.append(
                    (
                        "future-dates",
                        f"{rel}:{lineno} references {iso} (today is {today}). If this is a "
                        f"deadline, add it to KNOWN_FUTURE_DATES with a reason; if it describes "
                        f"completed work, the date is wrong.",
                    )
                )
    return fails


def _collected_counts() -> tuple[int, int]:
    """Ask pytest what actually exists rather than trusting a comment."""

    def count(target: str) -> int:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", target, "--collect-only", "-q", "--no-header"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        # `-q --collect-only` prints one `path/to/test_x.py: N` line per file and
        # does NOT print a "N tests collected" summary, so sum the per-file
        # counts. Parsing the wrong thing here silently reports 0, which would
        # disable the check rather than fail it — hence the explicit guard in
        # the caller.
        # Anchor to the target directory. A bare `<path>.py: <n>` pattern also
        # matches pytest's warnings-summary header
        # (`.../site-packages/fastapi/testclient.py:1`), which silently added a
        # phantom test and made this check report drift that did not exist —
        # a false alarm is how a gate earns the right to be ignored.
        prefix = target.replace("\\", "/").rstrip("/")
        total = 0
        for line in proc.stdout.splitlines():
            stripped = line.strip().replace("\\", "/")
            if not stripped.startswith(prefix):
                continue
            m = re.match(r"^\S+\.py:\s*(\d+)\s*$", stripped)
            if m:
                total += int(m.group(1))
        return total

    return count("tests/unit"), count("tests/integration")


def check_test_counts() -> list[Failure]:
    unit, integration = _collected_counts()
    if unit == 0:
        return [("test-counts", "collected 0 unit tests — cannot verify counts")]

    fails: list[Failure] = []
    claim = re.compile(r"(\d+)\s+unit\s*\+\s*(\d+)\s+integration", re.I)
    suite = re.compile(r"unit suite \((\d+) tests", re.I)
    # The bare "N unit tests" phrasing was uncovered until 0.9.3, which is how a
    # stale 57 survived in submission/DEVPOST.md across several sweeps.
    bare = re.compile(r"(\d+)\s+unit\s+tests", re.I)
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("CHANGELOG"):
            continue  # historical entries are allowed to state past counts

        # Scanned over the WHOLE document, not line by line. A claim that wraps
        # across a newline is still one claim, and the line-by-line version of
        # this loop could not see it: `submission/SUBMISSION.md` carried
        # "65 unit +\n      9 integration tests" through several releases while
        # this check reported green, because the two halves never shared a line.
        # The patterns already use `\s`, which matches the newline — only the
        # per-line iteration was wrong. Same failure shape as the bare-"N unit
        # tests" hole closed in 0.9.3: the gate was narrower than the prose.
        def _line_of(offset: int, _text: str = text) -> int:
            return _text.count("\n", 0, offset) + 1

        for m in claim.finditer(text):
            u, i = m.group(1), m.group(2)
            if (int(u), int(i)) != (unit, integration):
                fails.append(
                    (
                        "test-counts",
                        f"{rel}:{_line_of(m.start())} claims {u} unit + {i} integration; actual {unit} + {integration}",
                    )
                )
        for m in suite.finditer(text):
            if int(m.group(1)) != unit:
                fails.append(
                    ("test-counts", f"{rel}:{_line_of(m.start())} claims a {m.group(1)}-test unit suite; actual {unit}")
                )
        for m in bare.finditer(text):
            if int(m.group(1)) != unit:
                fails.append(
                    ("test-counts", f"{rel}:{_line_of(m.start())} claims {m.group(1)} unit tests; actual {unit}")
                )
    return fails


def check_adr_count() -> list[Failure]:
    """Every stated ADR count, however it is phrased.

    Three patterns, because the first one alone was not enough. Adding ADR 010
    left `README.md` reading "Nine decisions documented (001-009)" with no row
    for the new one, and this check reported green: it only matched the literal
    words "ADRs" / "Architecture Decision Records", so neither "N decisions
    documented" nor the range itself was ever looked at. The gate was narrower
    than the prose it was meant to police — the same shape as the wrapped-claim
    hole in check_test_counts.
    """
    actual = len(list((REPO_ROOT / "docs" / "adr").glob("[0-9]*.md")))
    fails: list[Failure] = []
    # The optional `-\w+` catches a hyphenated qualifier between the number and
    # the noun: "the nine-row ADR table" in submission/DEMO_SCRIPT.md went stale
    # on ADR 010 and slipped through, because the token adjacent to "ADR" was
    # "row" rather than a number.
    counted = [
        re.compile(r"\b(\w+)(?:-\w+)?\s+(?:ADRs?|Architecture Decision Records)\b", re.I),
        re.compile(r"\b(\w+)(?:-\w+)?\s+decisions?\s+documented\b", re.I),
    ]
    # "(001-009)" / "001 to 009" — the upper bound is a count claim too.
    ranges = re.compile(r"\b001\s*(?:[-–—]|to)\s*0*(\d+)\b")
    words = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    }  # fmt: skip
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("CHANGELOG"):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern in counted:
                for token in pattern.findall(line):
                    n = words.get(token.lower()) or (int(token) if token.isdigit() else None)
                    if n is not None and n != actual:
                        fails.append(("adr-count", f"{rel}:{lineno} says {token} ADRs; actual {actual}"))
            for hi in ranges.findall(line):
                if int(hi) != actual:
                    fails.append(("adr-count", f"{rel}:{lineno} claims the range ends at {hi}; actual {actual}"))
    return fails


def check_links() -> list[Failure]:
    link = re.compile(r"\[[^\]]*\]\(([^)#][^)]*)\)")
    fails: list[Failure] = []
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for target in link.findall(line):
                t = target.split("#")[0].strip()
                if not t or t.startswith(("http://", "https://", "mailto:")):
                    continue
                if not (path.parent / t).exists():
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    fails.append(("links", f"{rel}:{lineno} -> {t} does not exist"))
    return fails


def check_generated_files() -> list[Failure]:
    proc = subprocess.run(
        [sys.executable, "scripts/build_devpost_readme.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        return [("generated", "submission/DEVPOST_README.md is stale — run make devpost-readme")]
    return []


def check_resilience_suites() -> list[Failure]:
    """Every suite the report promises must actually be in the report.

    `docs/RESILIENCE.md` is generated, and Suite D used to be hand-written into
    it — so the 2026-08-07 bench run deleted the whole section and a release
    shipped with the README's failure-mode table pointing at a heading that no
    longer existed. Nothing noticed, because a missing section looks exactly
    like a section that was never promised. This asserts the promise.
    """
    path = REPO_ROOT / "docs" / "RESILIENCE.md"
    if not path.is_file():
        return [("resilience-suites", "docs/RESILIENCE.md does not exist")]
    text = path.read_text(encoding="utf-8")
    expected = {
        "A. Kill storm": "process killed mid-step",
        "B. Exactly-once under concurrency": "the exactly-once claim guard",
        "C. Vector search at scale": "C-SPANN vs full scan",
        "D. Deploy mid-incident": "code replaced under an open incident",
    }
    fails = []
    for heading, what in expected.items():
        if f"## {heading}" not in text:
            fails.append(("resilience-suites", f"docs/RESILIENCE.md has no '{heading}' section ({what})"))
    return fails


def check_lambda_manifest() -> list[Failure]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit/test_lambda_manifest.py", "-q", "--no-header"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        return [("lambda-manifest", "infra/requirements-lambda.txt has drifted from requirements.txt")]
    return []


# Directories the README's tree lists child-by-child. Adding a file to one of
# these and not to the tree is drift — which is how the tree ended up missing
# ten scripts, two asset families and the whole data/ directory at once. Dirs
# the tree deliberately collapses (tests/unit, docs/adr) are NOT listed here:
# the tree describes those by their job, and enumerating 8 test files would be
# noise that goes stale on every new test.
TREE_ENUMERATED_DIRS = (
    "agents",
    "scripts",
    "infra",
    "prompts",
    "assets",
    "data",
    "notebooks",
    ".github/workflows",
)
# Build outputs, caches and package plumbing — real files, but not structure a
# reader needs. Dunder names are skipped wholesale.
TREE_IGNORED_CHILDREN = {"__pycache__", "seed_embeddings.json"}


def _readme_tree() -> str:
    """The fenced block under ## Project Structure, comments stripped."""
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
    # Anchored on the heading, not on "continuum/" — that string also appears in
    # every GitHub badge URL on page one, and matching the first one silently
    # scanned the badge block instead of the tree.
    heading = text.index("## Project Structure")
    start = text.index("continuum/", heading)
    end = text.index("```", start)
    return text[start:end]


def _tree_tokens(tree: str) -> list[str]:
    tokens: list[str] = []
    for line in tree.splitlines():
        body = line.split("#", 1)[0]  # drop the annotation
        body = re.sub(r"^[│├└─\s]+", "", body).strip()
        if not body:
            continue
        # A line may name several siblings: "A.md · B.md · C.md"
        for token in body.split("·"):
            token = token.strip().rstrip("/")
            if token and not token.startswith("continuum"):
                tokens.append(token)
    return tokens


def check_project_tree() -> list[Failure]:
    """The README's Project Structure must describe the repo that exists.

    Two directions, because they fail differently: a token naming nothing is a
    move or delete nobody swept for, and a child missing from the tree is work
    that shipped without the map being updated. The second is the one that
    actually happened, and only a reader comparing the tree against `ls` would
    ever have caught it.
    """
    fails: list[Failure] = []
    tree = _readme_tree()

    real = [p for p in REPO_ROOT.rglob("*") if not any(part in SKIP_DIRS for part in p.parts)]
    names = {p.name for p in real}
    suffixes = {p.relative_to(REPO_ROOT).as_posix() for p in real}
    for token in _tree_tokens(tree):
        # Tokens are written relative to wherever they sit in the tree, so a
        # nested entry like `load/k6_smoke.js` resolves as a path suffix rather
        # than from the repo root.
        if (REPO_ROOT / token).exists() or token in names:
            continue
        if any(s == token or s.endswith("/" + token) for s in suffixes):
            continue
        fails.append(("project-tree", f"README's tree names {token}, which does not exist"))

    for dirname in TREE_ENUMERATED_DIRS:
        directory = REPO_ROOT / dirname
        if not directory.is_dir():
            fails.append(("project-tree", f"{dirname}/ is listed as enumerated but does not exist"))
            continue
        for child in sorted(directory.iterdir()):
            name = child.name
            if name.startswith((".", "__")) or name in TREE_IGNORED_CHILDREN:
                continue
            if name not in tree:
                fails.append(("project-tree", f"{dirname}/{name} is missing from README's Project Structure"))
    return fails


# --------------------------------------------------------------------------
# Paths named in prose, not as links. `check_links` only sees markdown link
# targets, so a path written as `assets/provider-evidence/15.foo.txt` inside
# backticks was invisible to it — which is how references to renumbered evidence
# files survived a rename. Anything that looks like a repo path and sits in
# inline code has to resolve.
_INLINE_PATH = re.compile(r"`([A-Za-z0-9_.][A-Za-z0-9_./-]*\.[A-Za-z0-9]{1,6})`")

# Prefixes worth policing: directories whose contents get renumbered, renamed or
# regenerated. Deliberately not "any path" — prose is full of `foo.py` examples,
# `*.jsonl` globs and filenames belonging to other projects.
_INLINE_PATH_ROOTS = ("assets/", "scripts/", "docs/", "infra/", "agents/", "submission/", "prompts/", "tests/")

# CHANGELOG.md is exempt, and that is not a loophole. Its entire job is to
# describe states the repo used to be in — "moved docs/SUBMISSION.md to
# submission/" names a path that must no longer exist for the entry to be true.
# Enforcing existence there would force history to be rewritten every time a
# file moves, which is the opposite of what a changelog is for.
_INLINE_PATH_EXEMPT_FILES = {"CHANGELOG.md"}

# A single line may opt out when it deliberately names something absent — a file
# that was removed, or one that does not exist yet. Mirrors the
# `drift-allow-future` marker above: the escape hatch is per-line and has to be
# typed on purpose, so it cannot silently cover a genuine stale reference on the
# next line.
_ALLOW_PATH_MARKER = "drift-allow-path"


def check_inline_paths() -> list[Failure]:
    """Repo paths written in backticks must exist, not just linked ones.

    `check_links` reads markdown link targets. A path mentioned in prose is
    invisible to it, so when the provider-evidence frames were renumbered the
    references to `15.lambda-cold-starts.txt` in three documents stayed green
    through a full release.
    """
    fails: list[Failure] = []
    for path in _markdown_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in _INLINE_PATH_EXEMPT_FILES:
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _ALLOW_PATH_MARKER in line:
                continue
            for token in _INLINE_PATH.findall(line):
                if not token.startswith(_INLINE_PATH_ROOTS):
                    continue
                if "*" in token or (REPO_ROOT / token).exists():
                    continue
                fails.append(
                    (
                        "inline-paths",
                        f"{rel}:{line_no} names `{token}`, which does not exist. If it was removed "
                        f"or does not exist yet, add a `{_ALLOW_PATH_MARKER}` comment to that line",
                    )
                )
    return fails


# --------------------------------------------------------------------------
# README.md is ALSO the Hugging Face Space's landing page, and
# .github/workflows/sync-to-hf-space.yml git-rm's every binary before pushing to
# the Hub. So a relative PNG renders on GitHub and 404s on the live demo — the
# first page a judge opens after the repo. SVGs are not stripped.
_HF_STRIPPED = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".mp4", ".mov", ".webm", ".mp3", ".wav", ".m4a")


def check_readme_binaries_are_absolute() -> list[Failure]:
    """Binary assets in README.md must use absolute URLs, or the Space breaks.

    Nothing else catches this: GitHub renders the relative path perfectly, CI is
    green, and the only symptom is a broken image on the public demo.
    """
    fails: list[Failure] = []
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    targets = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", readme)
    targets += re.findall(r'\b(?:src|srcset)="([^"]+)"', readme)
    for target in targets:
        if target.startswith(("http://", "https://", "data:")):
            continue
        if target.lower().endswith(_HF_STRIPPED):
            fails.append(
                (
                    "readme-binaries",
                    f"README.md embeds {target} by relative path — the HF sync strips binaries, "
                    "so this renders on GitHub and breaks on the Space. Use the raw.githubusercontent URL",
                )
            )
    return fails


# --------------------------------------------------------------------------
# The charts are generated from the newest resilience run. Docs that name which
# run they came from go stale the moment a newer run lands, and the number they
# attribute is then attached to the wrong evidence.


_ALLOW_RUN_MARKER = "drift-allow-run"


def check_chart_provenance() -> list[Failure]:
    """A doc naming the charts' source run must name the run they'd regenerate from.

    `submission/DEMO_SCRIPT.md` credited run `1f98a6fc` for a day after the
    charts had been rebuilt from `e765a3c5`. Both ids are real, both folders are
    committed, and every link resolved — only recomputing the source catches it.
    """
    runs_dir = REPO_ROOT / "assets" / "resilience-run"
    if not runs_dir.is_dir():
        return []
    known = {p.name for p in runs_dir.iterdir() if p.is_dir()}
    if not known:
        return []
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from build_charts import newest_run  # type: ignore[import-not-found]

        newest = newest_run().name
    except Exception as exc:  # noqa: BLE001 — a broken builder is its own failure, reported not raised
        return [("chart-provenance", f"could not resolve the newest resilience run: {type(exc).__name__}")]

    fails: list[Failure] = []
    # Scoped to lines about charts, plus the line before. Run ids are cited
    # legitimately elsewhere — COSTS.md attributes Request Unit spend to a
    # specific bench, and that stays true when a newer run lands. Only the
    # charts are *regenerated*, so only they can be miscredited.
    #
    # The first version of this pattern required the id within 80 non-dot
    # characters of "charts". It never fired: the real sentence is "Charts
    # present and committed (`assets/charts/*-16x9.png`, from evidence run
    # `…`)", and the `.` in the glob stopped the match dead. Found by testing
    # the check against the bug it was written for, which is the only way to
    # know a gate works.
    pattern = re.compile(r"evidence run `([0-9a-f]{8})`", re.I)
    for path in _markdown_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_no, line in enumerate(lines, 1):
            # Prose that *narrates* a past miscrediting has to name the wrong run
            # to make sense — CLAUDE.md documents this very failure. Same
            # per-line, typed-on-purpose escape hatch as the other two checks.
            if _ALLOW_RUN_MARKER in line:
                continue
            context = (lines[line_no - 2] if line_no >= 2 else "") + line
            if "chart" not in context.lower():
                continue
            for cited in pattern.findall(line):
                if cited in known and cited != newest:
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    fails.append(
                        (
                            "chart-provenance",
                            f"{rel}:{line_no} credits the charts to run `{cited}`, but they regenerate from `{newest}`",
                        )
                    )
    return fails


CHECKS = [
    ("version fields agree", check_versions),
    ("no future-dated references", check_no_future_dates),
    ("stated test counts are real", check_test_counts),
    ("stated ADR count is real", check_adr_count),
    ("relative links resolve", check_links),
    ("generated files current", check_generated_files),
    ("resilience report has every suite", check_resilience_suites),
    ("lambda manifest in sync", check_lambda_manifest),
    ("README project tree matches the repo", check_project_tree),
    ("paths named in prose exist", check_inline_paths),
    ("README binaries use absolute URLs", check_readme_binaries_are_absolute),
    ("charts credited to the run they came from", check_chart_provenance),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args()

    all_failures: list[Failure] = []
    if not args.quiet:
        print("Continuum — documentation drift check\n")

    for label, fn in CHECKS:
        try:
            failures = fn()
        except Exception as exc:  # noqa: BLE001 — a broken check must not pass silently
            failures = [(label, f"check itself failed: {type(exc).__name__}: {exc}")]
        all_failures.extend(failures)
        if not args.quiet:
            print(f"  [{'FAIL' if failures else 'OK  '}] {label}")
            for _, detail in failures:
                print(f"          {detail}")

    if all_failures:
        print(f"\n{len(all_failures)} drift issue(s). Docs disagree with the repo.")
        return 1
    if not args.quiet:
        print("\nNo drift. Docs agree with the repo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
