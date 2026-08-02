"""
Integration test — proves the disaster-recovery snapshot actually restores.

`scripts/export_memory.py` is the insurance against the CockroachDB Basic org
being deleted when trial credits lapse (submission/COSTS.md). For a while it
shipped without a restore path at all: its own `_meta.note` pointed at a
`seed_memory.py --from-snapshot` flag that did not exist. An export nobody has
restored is a file, not a backup — so this test does the round trip against a
real cluster and schema.

What it proves that a unit test cannot: the exported JSON survives re-insertion
into the real column types. `detail` JSONB has to come back as a dict rather
than a string, and the embedding — exported as a plain float list so restoring
never needs Bedrock — has to be accepted by `VECTOR(1024)` and still be usable
as a `<->` search operand afterwards. Restoring a vector that no longer answers
a nearest-neighbour query would look like a successful restore and be a dead
memory layer.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Json

from scripts.export_memory import export
from scripts.restore_memory import read_snapshot, restore

pytestmark = pytest.mark.skipif(
    "COCKROACH_DATABASE_URL" not in os.environ,
    reason="requires a live CockroachDB instance — set COCKROACH_DATABASE_URL to run",
)

DIMS = 1024


def _vector(seed: float) -> list[float]:
    """A deterministic unit-ish vector — no Bedrock call, which is the point."""
    return [seed] + [0.0] * (DIMS - 1)


def _seed_rows(conn, correlation_id: str) -> uuid.UUID:
    """Write one incident + step + embedding directly.

    Deliberately raw SQL rather than memory_agent: this test is about the
    snapshot's fidelity to the *schema*, and it needs to control fields
    (`detail` shape, embedding value) that the agent's API does not expose.
    """
    incident_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO incidents (incident_id, correlation_id, service, region, severity, state, summary) "
            "VALUES (%s, %s, 'checkout-api', 'eu-central-1', 'high', 'resolved', %s)",
            (incident_id, correlation_id, "snapshot round-trip test incident"),
        )
        cur.execute(
            "INSERT INTO remediation_steps (incident_id, step_index, action, status, detail) "
            "VALUES (%s, 0, 'restart_connection_pool', 'executed', %s)",
            (incident_id, Json({"reasoning_source": "bedrock", "nested": {"distance": 0.1234}})),
        )
        cur.execute(
            "INSERT INTO incident_embeddings (incident_id, service, region, embedding, embedding_model) "
            "VALUES (%s, 'checkout-api', 'eu-central-1', %s::vector, 'roundtrip-test')",
            (incident_id, "[" + ",".join(str(v) for v in _vector(0.5)) + "]"),
        )
    conn.commit()
    return incident_id


def _delete(conn, incident_id: uuid.UUID) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM remediation_steps WHERE incident_id = %s", (incident_id,))
        cur.execute("DELETE FROM incident_embeddings WHERE incident_id = %s", (incident_id,))
        cur.execute("DELETE FROM incidents WHERE incident_id = %s", (incident_id,))
    conn.commit()


@pytest.fixture
def snapshot_incident(correlation_id, tmp_path):
    """Seed a known incident, yield it, and guarantee cleanup even on failure."""
    url = os.environ["COCKROACH_DATABASE_URL"]
    with psycopg.connect(url) as conn:
        incident_id = _seed_rows(conn, correlation_id)
    yield incident_id, tmp_path
    with psycopg.connect(url) as conn:
        _delete(conn, incident_id)


def test_export_restore_round_trip_preserves_rows(snapshot_incident):
    """Export, delete the rows, restore — the durable state comes back intact."""
    incident_id, tmp_path = snapshot_incident
    url = os.environ["COCKROACH_DATABASE_URL"]
    out = tmp_path / "snapshot.jsonl"

    export(out)

    parsed = read_snapshot(out)
    exported_ids = {r["incident_id"] for r in parsed["incidents"]}
    assert str(incident_id) in exported_ids, "seeded incident missing from the snapshot"

    with psycopg.connect(url) as conn:
        _delete(conn, incident_id)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM incidents WHERE incident_id = %s", (incident_id,))
            assert cur.fetchone()[0] == 0, "precondition: rows should be gone before restore"

    restore(out, url=url)

    with psycopg.connect(url) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT state, severity, summary FROM incidents WHERE incident_id = %s", (incident_id,))
        incident = cur.fetchone()
        assert incident is not None, "incident was not restored"
        assert incident["state"] == "resolved"
        assert incident["severity"] == "high"

        cur.execute(
            "SELECT action, status, detail FROM remediation_steps WHERE incident_id = %s ORDER BY step_index",
            (incident_id,),
        )
        steps = cur.fetchall()
        assert len(steps) == 1
        assert steps[0]["action"] == "restart_connection_pool"
        # The interesting rows in this dataset are the ones a chaos run left
        # behind, so `status` and `detail` have to survive verbatim — a restore
        # that resets every step to 'proposed' would lose the evidence.
        assert steps[0]["status"] == "executed"
        detail = steps[0]["detail"]
        assert isinstance(detail, dict), f"detail came back as {type(detail)}, not JSONB"
        assert detail["reasoning_source"] == "bedrock"
        assert detail["nested"]["distance"] == pytest.approx(0.1234)


def test_restored_embedding_still_answers_a_vector_search(snapshot_incident):
    """A restored vector must remain a usable `<->` operand, not just a stored blob."""
    incident_id, tmp_path = snapshot_incident
    url = os.environ["COCKROACH_DATABASE_URL"]
    out = tmp_path / "snapshot.jsonl"

    export(out)
    with psycopg.connect(url) as conn:
        _delete(conn, incident_id)
    restore(out, url=url)

    probe = "[" + ",".join(str(v) for v in _vector(0.5)) + "]"
    with psycopg.connect(url) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT incident_id, embedding <-> %s::vector AS distance "
            "FROM incident_embeddings WHERE service = 'checkout-api' "
            "ORDER BY embedding <-> %s::vector LIMIT 5",
            (probe, probe),
        )
        rows = cur.fetchall()

    restored = [r for r in rows if str(r["incident_id"]) == str(incident_id)]
    assert restored, "restored embedding did not rank for its own exact vector"
    # Exact same vector in and out — any float mangling in the JSONL round trip
    # shows up here as a non-zero distance.
    assert restored[0]["distance"] == pytest.approx(0.0, abs=1e-6)


def test_restore_is_idempotent(snapshot_incident):
    """Restoring twice must not duplicate rows — ON CONFLICT DO NOTHING throughout."""
    incident_id, tmp_path = snapshot_incident
    url = os.environ["COCKROACH_DATABASE_URL"]
    out = tmp_path / "snapshot.jsonl"

    export(out)
    restore(out, url=url)  # into a cluster that still has every row
    restore(out, url=url)

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM incidents WHERE incident_id = %s", (incident_id,))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM remediation_steps WHERE incident_id = %s", (incident_id,))
        assert cur.fetchone()[0] == 1


def test_snapshot_meta_points_at_a_real_restore_command(tmp_path):
    """The snapshot's own instructions must name a command that exists.

    This regressed once: `_meta.note` advertised `seed_memory.py --from-snapshot`,
    a flag that was never implemented, so the only documentation a future
    restorer would find was wrong.
    """
    out = tmp_path / "snapshot.jsonl"
    export(out)
    meta = json.loads(out.read_text(encoding="utf-8").splitlines()[0])["_meta"]
    assert "restore_memory.py" in meta["note"]
    assert Path("scripts/restore_memory.py").exists()
