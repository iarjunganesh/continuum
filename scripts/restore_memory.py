"""
Restore a CockroachDB memory snapshot produced by scripts/export_memory.py.

The other half of the insurance. `export_memory.py` existed on its own for a
while, which meant the snapshot was a file nobody had ever restored — the same
"code that has never run is unproven" trap this project keeps rediscovering. A
backup you cannot demonstrate restoring is not a backup.

Restores exact durable rows rather than re-deriving them: step `status`,
`detail`, and timestamps come back as they were, because the interesting rows in
this dataset are the ones a chaos run produced. That is why this is not a flag on
seed_memory.py — that script *synthesizes* a fresh incident history from a
seed file, which is a different job with a different input format.

Every insert is ON CONFLICT DO NOTHING, so restoring into a populated cluster is
a no-op rather than a corruption, and re-running after a partial failure resumes.
Needs no AWS credentials: embeddings travel in the snapshot as plain float lists.

Usage:
    python scripts/restore_memory.py --file data/snapshots/memory-YYYYMMDD-HHMM.jsonl
    python scripts/restore_memory.py --file ... --url postgresql://...   # restore elsewhere
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402
from observability.structured_logger import get_logger  # noqa: E402

log = get_logger(__name__)

# Bulk vector inserts contend on C-SPANN partition metadata and surface as
# serialization failures under SERIALIZABLE — the resilience benchmark learned
# this by orphaning ~1,500 rows when its cleanup gave up on the first retry.
# Commit in chunks and back off rather than restoring 40% of a snapshot.
CHUNK_ROWS = 100
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 0.5

# Ordered: remediation_steps and incident_embeddings both carry a foreign key to
# incidents, so the parent rows have to land first regardless of file order.
TABLE_ORDER = ("incidents", "remediation_steps", "incident_embeddings")

_INSERTS: dict[str, str] = {
    "incidents": """
        INSERT INTO incidents (incident_id, correlation_id, service, region, severity,
                               state, summary, opened_at, updated_at, resolved_at, synthetic)
        VALUES (%(incident_id)s, %(correlation_id)s, %(service)s, %(region)s, %(severity)s,
                %(state)s, %(summary)s, %(opened_at)s, %(updated_at)s, %(resolved_at)s, %(synthetic)s)
        ON CONFLICT (incident_id) DO NOTHING
    """,
    "remediation_steps": """
        INSERT INTO remediation_steps (step_id, incident_id, step_index, action,
                                       proposed_by, status, detail, created_at)
        VALUES (%(step_id)s, %(incident_id)s, %(step_index)s, %(action)s,
                %(proposed_by)s, %(status)s, %(detail)s, %(created_at)s)
        ON CONFLICT (incident_id, step_index) DO NOTHING
    """,
    "incident_embeddings": """
        INSERT INTO incident_embeddings (incident_id, service, region, embedding, embedding_model, created_at)
        VALUES (%(incident_id)s, %(service)s, %(region)s, %(embedding)s::vector,
                %(embedding_model)s, %(created_at)s)
        ON CONFLICT (incident_id) DO NOTHING
    """,
}


def read_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Parse a snapshot into per-table row lists, skipping the `_meta` header."""
    rows: dict[str, list[dict[str, Any]]] = {t: [] for t in TABLE_ORDER}
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "_meta" in rec:
                continue
            table = rec.get("table")
            if table not in rows:
                raise ValueError(f"{path}:{line_no}: unknown table {table!r}")
            rows[table].append(_coerce(table, rec["row"]))
    return rows


def _coerce(table: str, row: dict[str, Any]) -> dict[str, Any]:
    """Normalise a JSON row back into what psycopg needs for its INSERT."""
    row = dict(row)
    if table == "remediation_steps":
        # JSONB round-trips through the snapshot as a dict; psycopg needs the
        # Json adapter to put it back, and NULL detail must stay NULL.
        row["detail"] = Json(row["detail"]) if row.get("detail") is not None else None
    if table == "incident_embeddings":
        emb = row.get("embedding")
        # export_memory.py normalises to a float list, but accept the pgvector
        # string form too so a hand-edited or older snapshot still restores.
        if isinstance(emb, list):
            row["embedding"] = "[" + ",".join(str(v) for v in emb) + "]"
    return row


def _execute_chunk(conn: psycopg.Connection, sql: str, chunk: list[dict[str, Any]]) -> None:
    for attempt in range(MAX_RETRIES):
        try:
            with conn.cursor() as cur:
                cur.executemany(sql, chunk)
            conn.commit()
            return
        except psycopg.errors.SerializationFailure:
            conn.rollback()
            wait = BACKOFF_BASE_SECONDS * (2**attempt)
            log.warning("restore_chunk_retrying", attempt=attempt + 1, wait_seconds=wait, rows=len(chunk))
            time.sleep(wait)
    raise RuntimeError(f"chunk of {len(chunk)} rows still failing after {MAX_RETRIES} retries")


def restore(path: Path, url: str | None = None) -> dict[str, int]:
    rows = read_snapshot(path)
    counts = {t: 0 for t in TABLE_ORDER}

    with psycopg.connect(url or settings.cockroach_database_url) as conn:
        for table in TABLE_ORDER:
            table_rows = rows[table]
            for start in range(0, len(table_rows), CHUNK_ROWS):
                chunk = table_rows[start : start + CHUNK_ROWS]
                _execute_chunk(conn, _INSERTS[table], chunk)
                counts[table] += len(chunk)

    log.info("memory_restored", source=str(path), **counts)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="snapshot JSONL from scripts/export_memory.py")
    parser.add_argument("--url", help="target cluster (defaults to $COCKROACH_DATABASE_URL)")
    args = parser.parse_args()

    counts = restore(Path(args.file), url=args.url)
    print(f"restored from {args.file}")
    for table, n in counts.items():
        print(f"  {table}: {n}")
