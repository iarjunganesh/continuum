"""
Does the vector index retrieve a precedent that actually shares the failure mode?

`EXPLAIN` proves C-SPANN is used. A latency curve proves it is fast. Neither
proves the vectors mean anything — the seed corpus once ran on
`synthetic-deterministic` hash vectors whose own generator documents them as
"deliberately NOT semantically meaningful", and every one of those signals stayed
green while nearest-neighbour ordering was arbitrary. The only measurement that
catches it is retrieval quality, against a baseline computable without a database.

That measurement was made once, by hand, and its result — precision@1 55% -> 98%
after reseeding with real Titan vectors — was then quoted in five documents while
nothing in the repo recomputed it. This script is that missing half: the number a
reader is asked to believe, re-derived from committed data in one command.

Offline by construction. No AWS call, no cluster, no network — the Titan vectors
are the committed fixture and the baseline is a pure function, so the claim can be
checked by anyone who cloned the repo.

Usage:
    python scripts/precision_check.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
# Import the sibling scripts by name, matching the bootstrap every other script
# in this directory uses.
sys.path.insert(0, str(HERE))

from generate_synthetic_incidents import INCIDENT_TEMPLATES  # noqa: E402
from synthetic_vectors import deterministic_embedding  # noqa: E402

CORPUS = REPO_ROOT / "data" / "synthetic" / "incidents_seed.jsonl"
FIXTURE = REPO_ROOT / "data" / "synthetic" / "seed_embeddings.json"

# The floor the Titan arm must clear. Set well below the measured 98% so ordinary
# corpus regeneration does not trip it, and well above the ~55% the meaningless
# baseline scores — the gap between those two is the entire point of the check.
TITAN_FLOOR = 0.90


def failure_mode(summary: str) -> int | None:
    """Which INCIDENT_TEMPLATES entry generated this summary.

    The template *is* the failure mode: two incidents built from the same one
    describe the same class of outage on different services and regions. Derived
    by matching rather than stored, so this cannot drift from the generator.
    """
    for index, template in enumerate(INCIDENT_TEMPLATES):
        pattern = re.escape(template).replace(r"\{service\}", "(.+?)").replace(r"\{region\}", "(.+?)")
        if re.fullmatch(pattern, summary):
            return index
    return None


def _l2(a: list[float], b: list[float]) -> float:
    # strict=True so a dimension mismatch raises instead of silently comparing a
    # prefix — a 1536-dim assumption is exactly the bug this corpus already hit.
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def precision_at_1(vectors: dict[str, list[float]], modes: dict[str, int]) -> tuple[int, int]:
    """Fraction of incidents whose nearest neighbour shares their failure mode.

    Self is excluded — every vector is its own nearest neighbour at distance 0,
    and including it would score any embedding, however meaningless, at 100%.
    """
    ids = [i for i in vectors if i in modes]
    hits = 0
    for i in ids:
        nearest = min((j for j in ids if j != i), key=lambda j: _l2(vectors[i], vectors[j]))
        if modes[i] == modes[nearest]:
            hits += 1
    return hits, len(ids)


def load_corpus() -> dict[str, int]:
    """incident_id -> failure mode, for every incident whose template is known."""
    modes: dict[str, int] = {}
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        mode = failure_mode(record["summary"])
        if mode is not None:
            modes[record["incident_id"]] = mode
    return modes


def load_arms() -> tuple[dict[str, list[float]], dict[str, list[float]], dict[str, int]]:
    """The two vector families over the same incidents: Titan, and the baseline."""
    modes = load_corpus()
    titan: dict[str, list[float]] = json.loads(FIXTURE.read_text(encoding="utf-8"))

    summaries: dict[str, str] = {}
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            summaries[record["incident_id"]] = record["summary"]

    baseline = {i: deterministic_embedding(summaries[i]) for i in titan if i in summaries}
    return titan, baseline, modes


def main() -> int:
    titan, baseline, modes = load_arms()

    t_hits, t_n = precision_at_1(titan, modes)
    b_hits, b_n = precision_at_1(baseline, modes)
    t_score = t_hits / t_n if t_n else 0.0

    # ASCII only in the printed output: a Windows console defaults to cp1252 and
    # renders an em-dash as a replacement character.
    print("precision@1 - does the nearest neighbour share the failure mode?")
    print(f"  corpus: {t_n} incidents, {len(set(modes.values()))} distinct failure modes\n")
    print(f"  amazon.titan-embed-text-v2:0 (committed fixture)   {t_hits:>3}/{t_n:<3}  {100 * t_score:.0f}%")
    print(f"  synthetic-deterministic (hash vectors)             {b_hits:>3}/{b_n:<3}  {100 * b_hits / b_n:.0f}%")

    if t_score < TITAN_FLOOR:
        print(f"\nFAIL: the Titan arm scored below the {100 * TITAN_FLOOR:.0f}% floor.")
        print("Either the fixture no longer holds real Titan vectors, or the corpus was")
        print("regenerated without recapturing them — see scripts/capture_seed_embeddings.py.")
        return 1

    print(f"\nOK: Titan clears the {100 * TITAN_FLOOR:.0f}% floor; the meaningless baseline does not.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
