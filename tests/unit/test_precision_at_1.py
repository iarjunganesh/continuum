"""Retrieval quality is a claim, so it gets a test.

`precision@1 55% -> 98%` is quoted in the README, the changelog and both
submission documents as evidence that the vector index retrieves precedent that
*means* something. It was measured once by hand and then never recomputed, which
is the same failure mode as the bug it describes: a number everyone trusts and
nothing checks.

These tests recompute it from committed data on every push. They need no cluster,
no AWS call and no network — the Titan vectors are a committed fixture and the
baseline is a pure function.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import precision_check  # noqa: E402


def test_titan_fixture_clears_the_floor():
    """The committed Titan vectors retrieve a same-failure-mode precedent."""
    titan, _, modes = precision_check.load_arms()
    hits, total = precision_check.precision_at_1(titan, modes)

    assert total >= 40, "the seed corpus shrank — the published figure no longer describes it"
    assert hits / total >= precision_check.TITAN_FLOOR, (
        f"precision@1 fell to {hits}/{total}. Either the fixture no longer holds real Titan "
        "vectors, or the corpus was regenerated without recapturing them."
    )


def test_meaningless_vectors_score_materially_worse():
    """The baseline is what makes the Titan number mean anything.

    If hash vectors scored as well, precision@1 would be measuring the corpus's
    structure rather than the embedding's semantics, and the whole claim would be
    an artifact. The gap is the evidence.
    """
    titan, baseline, modes = precision_check.load_arms()

    t_hits, t_total = precision_check.precision_at_1(titan, modes)
    b_hits, b_total = precision_check.precision_at_1(baseline, modes)

    assert b_total == t_total, "the two arms must cover the same incidents to be comparable"
    assert b_hits / b_total < 0.75, (
        "the deliberately-meaningless baseline scored too well — precision@1 is not "
        "discriminating between semantic and arbitrary vectors on this corpus"
    )
    assert t_hits > b_hits


def test_failure_mode_is_derived_from_the_generator_not_restated():
    """Every seeded summary maps to a template, so the taxonomy cannot drift.

    `failure_mode` matches against the generator's own INCIDENT_TEMPLATES rather
    than a copy. A summary that matches nothing means the generator changed and
    this check silently stopped covering part of the corpus.
    """
    modes = precision_check.load_corpus()
    corpus_lines = [ln for ln in precision_check.CORPUS.read_text(encoding="utf-8").splitlines() if ln.strip()]

    assert len(modes) == len(corpus_lines), "some summaries matched no template — the taxonomy drifted"
    assert len(set(modes.values())) > 1, "a single failure mode makes precision@1 meaningless"
