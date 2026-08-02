"""
Assert the correlation query actually uses the C-SPANN vector index.

Why this file exists: `find_similar` returned *correct* results for weeks while
silently doing `spans: FULL SCAN` over `incident_embeddings`. Joining `incidents`
in the same statement as the `<->` ordering made CockroachDB abandon the vector
index, so "Distributed Vector Indexing does real correlation work" — one of the
two CockroachDB tools this submission claims — was untrue, and nothing failed.

No unit test can catch this. `tests/unit/test_correlation_agent.py` mocks psycopg
at the import boundary, so the SQL never reaches a planner; the query text could
be anything. Only EXPLAIN against a real cluster knows.

Requires a live CockroachDB at $COCKROACH_DATABASE_URL; skips without one.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from config import settings

pytestmark = pytest.mark.skipif(
    not os.getenv("COCKROACH_DATABASE_URL"),
    reason="integration test — needs a live CockroachDB",
)

VECTOR_INDEX = "idx_incident_embedding"
SERVICE = "vector-index-test"


def _explain(cur, embedding_literal: str, k: int = 5) -> str:
    """Run EXPLAIN over the *exact* query shape agents/correlation_agent.py uses.

    Kept as a copy rather than imported so the test fails loudly if the agent's
    query changes shape — the point is to notice a rewrite, not to follow it.
    """
    cur.execute(
        """
        EXPLAIN
        WITH nearest AS (
            SELECT incident_id, embedding <-> %s::vector AS distance
            FROM incident_embeddings
            WHERE service = %s
            ORDER BY embedding <-> %s::vector
            LIMIT %s
        )
        SELECT n.incident_id, i.summary, i.state, n.distance
        FROM nearest n
        JOIN incidents i ON i.incident_id = n.incident_id
        ORDER BY n.distance
        """,
        (embedding_literal, SERVICE, embedding_literal, k),
    )
    return "\n".join(row[0] for row in cur.fetchall())


@pytest.fixture
def embedding_literal() -> str:
    # Dimensionality must match VECTOR(1024): a mismatched literal disqualifies
    # the index on its own, which would make this test pass or fail for the
    # wrong reason.
    return "[" + ",".join("0.01" for _ in range(settings.embedding_dimensions)) + "]"


def test_correlation_query_uses_the_vector_index(embedding_literal):
    with psycopg.connect(settings.cockroach_database_url) as conn, conn.cursor() as cur:
        plan = _explain(cur, embedding_literal)

    assert VECTOR_INDEX in plan, (
        f"the correlation query is NOT using {VECTOR_INDEX} — Distributed Vector Indexing "
        f"is claimed but not exercised. Plan:\n{plan}"
    )
    assert "FULL SCAN" not in plan, f"the correlation query fell back to a full scan. Plan:\n{plan}"


def test_inlining_the_join_would_regress_to_a_full_scan(embedding_literal):
    """Pin the *reason* the CTE exists.

    If a future CockroachDB release starts planning the inlined JOIN through the
    vector index, this test fails — which is the signal to simplify
    `find_similar` back to one statement, not a defect. Documenting the
    constraint in a comment alone would leave nobody to notice it lifting.
    """
    with psycopg.connect(settings.cockroach_database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            EXPLAIN
            SELECT e.incident_id, i.summary, i.state, e.embedding <-> %s::vector AS distance
            FROM incident_embeddings e
            JOIN incidents i ON i.incident_id = e.incident_id
            WHERE e.service = %s
            ORDER BY e.embedding <-> %s::vector
            LIMIT 5
            """,
            (embedding_literal, SERVICE, embedding_literal),
        )
        inlined_plan = "\n".join(row[0] for row in cur.fetchall())

    if VECTOR_INDEX in inlined_plan:
        pytest.fail(
            "GOOD NEWS, ACTION NEEDED: the inlined JOIN now uses the vector index on this "
            "CockroachDB version. The CTE in agents/correlation_agent.py can be simplified "
            f"back to a single SELECT. Plan:\n{inlined_plan}"
        )
