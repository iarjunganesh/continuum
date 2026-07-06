"""
Deterministic synthetic embeddings — a Bedrock-free stand-in for Titan vectors.

The demo Space and the benchmark script both need a populated vector table, but
this account's Bedrock quota is throttled (ADR 008), so requiring a live embed
call to see *any* incidents makes the demo hostage to an AWS-side issue. This
maps text -> a stable 1024-dim unit vector with no external call: same text
gives the same vector, different text gives a different direction.

It is deliberately NOT semantically meaningful — nearest-neighbour ordering is
arbitrary. Its only jobs are (1) let the Space render populated offline and
(2) give `find_similar` a real vector to range over in benchmarks. For honest,
semantically-ranked correlation, capture real Titan vectors once with
scripts/capture_seed_embeddings.py and seed with --from-fixture.
"""
from __future__ import annotations

import hashlib
import math


def deterministic_embedding(text: str, dims: int = 1024) -> list[float]:
    """A stable, normalized `dims`-dimension vector derived from `text`.

    Unit L2 norm, matching Titan Text Embeddings V2's `normalize=True`, so it
    drops into the `VECTOR(1024)` column and `<->` distance queries unchanged.
    """
    raw = bytearray()
    counter = 0
    while len(raw) < dims:
        raw.extend(hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest())
        counter += 1
    vals = [(b / 127.5) - 1.0 for b in raw[:dims]]          # bytes -> [-1, 1]
    norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / norm for v in vals]
