"""
Export the CockroachDB memory layer to a portable JSONL snapshot.

Insurance, not a backup product. The demo cluster is a CockroachDB Basic org on
trial credits; if those lapse without a payment method the whole organization is
deleted after a grace period, unrestorably (see submission/COSTS.md). The
dataset is small enough that a plain export removes that as an existential risk:
re-seed a fresh cluster from this file and the demo is back.

Round-trips with scripts/seed_memory.py's schema expectations. Embeddings are
exported as plain float lists so the snapshot stays readable and diffable, and
so restoring never needs Bedrock.

Usage:
    python scripts/export_memory.py                       # -> data/snapshots/
    python scripts/export_memory.py --out data/snapshots/pre-expiry.jsonl
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402
from observability.structured_logger import get_logger  # noqa: E402

log = get_logger(__name__)


# Benchmark fixtures are transient and must never enter a snapshot. The first
# run of this script captured 1,044 incidents and 14.6 MB because a vector-scale
# benchmark happened to be mid-flight — a snapshot of the demo cluster should be
# the demo's data, not whatever was being measured at the time.
_BENCH_PREFIXES = ("resbench", "bench-", "deploy-smoke")
_BENCH_SERVICES = ("vector-scale-bench", "resilience-bench", "bench-service")

_INCIDENT_FILTER = "WHERE NOT (" + " OR ".join(f"correlation_id LIKE '{p}%'" for p in _BENCH_PREFIXES) + ")"


def export(out_path: Path) -> dict[str, int]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    counts = {"incidents": 0, "remediation_steps": 0, "incident_embeddings": 0}

    with (
        psycopg.connect(settings.cockroach_database_url) as conn,
        conn.cursor(row_factory=dict_row) as cur,
        out_path.open("w", encoding="utf-8") as fh,
    ):
        fh.write(
            json.dumps(
                {
                    "_meta": {
                        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "note": "Continuum memory snapshot. Restore with scripts/seed_memory.py --from-snapshot.",
                    }
                }
            )
            + "\n"
        )

        cur.execute(f"SELECT * FROM incidents {_INCIDENT_FILTER} ORDER BY opened_at")
        for row in cur.fetchall():
            counts["incidents"] += 1
            fh.write(json.dumps({"table": "incidents", "row": row}, default=str) + "\n")

        cur.execute(
            "SELECT s.* FROM remediation_steps s JOIN incidents i USING (incident_id) "
            f"{_INCIDENT_FILTER.replace('correlation_id', 'i.correlation_id')} "
            "ORDER BY s.incident_id, s.step_index"
        )
        for row in cur.fetchall():
            counts["remediation_steps"] += 1
            fh.write(json.dumps({"table": "remediation_steps", "row": row}, default=str) + "\n")

        # `embedding` comes back as a pgvector string like "[0.1,0.2,...]";
        # normalise to a float list so the snapshot is restorable without
        # depending on how psycopg renders the type.
        services = ", ".join(f"'{s}'" for s in _BENCH_SERVICES)
        cur.execute(f"SELECT * FROM incident_embeddings WHERE service NOT IN ({services})")
        for row in cur.fetchall():
            emb = row.get("embedding")
            if isinstance(emb, str):
                row["embedding"] = [float(x) for x in emb.strip("[]").split(",") if x]
            counts["incident_embeddings"] += 1
            fh.write(json.dumps({"table": "incident_embeddings", "row": row}, default=str) + "\n")

    log.info("memory_exported", out=str(out_path), **counts)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    default = f"data/snapshots/memory-{dt.datetime.now(dt.timezone.utc):%Y%m%d-%H%M}.jsonl"
    parser.add_argument("--out", default=default)
    args = parser.parse_args()

    counts = export(Path(args.out))
    size_kb = Path(args.out).stat().st_size / 1024
    print(f"exported to {args.out} ({size_kb:.0f} KB)")
    for table, n in counts.items():
        print(f"  {table}: {n}")
