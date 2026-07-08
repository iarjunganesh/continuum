"""
Latency benchmarks for Continuum's CockroachDB memory operations.

Measures the operations the recovery guarantee actually depends on, against a
live cluster at $COCKROACH_DATABASE_URL — no Bedrock needed (vector search uses
deterministic synthetic vectors, synthetic_vectors.py). Creates its own
`bench-*` incidents and deletes them afterwards. Writes a Markdown table to
docs/BENCHMARKS.md and prints it.

Usage:
    python scripts/benchmark.py                 # 50 iterations -> docs/BENCHMARKS.md
    python scripts/benchmark.py --n 200 --out docs/BENCHMARKS.md
"""
import argparse
import datetime as dt
import os
import statistics
import sys
import time
import uuid

import psycopg

# Running as `python scripts/benchmark.py` puts scripts/ (not the repo root)
# on sys.path, so agents/config/observability won't import otherwise.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthetic_vectors import deterministic_embedding  # noqa: E402

from agents.correlation_agent import CorrelationAgent  # noqa: E402
from agents.memory_agent import MemoryAgent  # noqa: E402
from config import settings  # noqa: E402
from observability.structured_logger import get_logger  # noqa: E402

log = get_logger(__name__)

SERVICE = "bench-service"
REGION = "eu-central-1"


def _pctl(samples_ms: list[float], p: float) -> float:
    s = sorted(samples_ms)
    if not s:
        return 0.0
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _bench(fn, n: int) -> list[float]:
    samples = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1000.0)
    return samples


def run(n: int, out_path: str, context: str) -> None:
    memory = MemoryAgent()
    correlation = CorrelationAgent()
    dsn = settings.cockroach_database_url
    prefix = f"bench-{uuid.uuid4().hex[:8]}"
    created: list[tuple] = []  # (incident_id, correlation_id)

    # --- setup: a pool of incidents + deterministic embeddings so the read and
    #     vector-search benchmarks range over realistic data ---
    for i in range(n):
        cid = f"{prefix}-{i}"
        iid = memory.open_incident(cid, SERVICE, REGION, "high", f"benchmark incident {i}")
        created.append((iid, cid))
        vec = "[" + ",".join(str(v) for v in deterministic_embedding(f"benchmark incident {i}")) + "]"
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO incident_embeddings (incident_id, service, region, embedding, embedding_model) "
                "VALUES (%s, %s, %s, %s::vector, %s) ON CONFLICT (incident_id) DO NOTHING",
                (iid, SERVICE, REGION, vec, "synthetic-deterministic"),
            )
            conn.commit()

    results: dict[str, list[float]] = {}
    query_vec = deterministic_embedding("benchmark query vector")

    results["recovery read (get_open_incident)"] = _bench(
        lambda: memory.get_open_incident(created[0][1]), n)
    results["vector search (find_similar, k=5)"] = _bench(
        lambda: correlation.find_similar(SERVICE, query_vec), n)

    start_ms, done_ms, resume_ms = [], [], []
    for iid, cid in created:
        t = time.perf_counter()
        memory.checkpoint_step_start(iid, 0, "bench_action")
        start_ms.append((time.perf_counter() - t) * 1000.0)
        t = time.perf_counter()
        memory.checkpoint_step_done(iid, 0)
        done_ms.append((time.perf_counter() - t) * 1000.0)
        # end-to-end resume: leave step 1 executing, recovery-read, re-run, finish
        memory.checkpoint_step_start(iid, 1, "bench_action_1")
        t = time.perf_counter()
        memory.get_open_incident(cid)
        memory.checkpoint_step_start(iid, 1, "bench_action_1", resuming=True)
        memory.checkpoint_step_done(iid, 1)
        resume_ms.append((time.perf_counter() - t) * 1000.0)
    results["step-start commit (checkpoint_step_start)"] = start_ms
    results["step-done commit (checkpoint_step_done)"] = done_ms
    results["end-to-end resume (recovery read + re-run step)"] = resume_ms

    # --- cleanup ---
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for iid, _ in created:
            cur.execute("DELETE FROM remediation_steps WHERE incident_id = %s", (iid,))
            cur.execute("DELETE FROM incident_embeddings WHERE incident_id = %s", (iid,))
            cur.execute("DELETE FROM incidents WHERE incident_id = %s", (iid,))
        conn.commit()

    _write(results, n, out_path, context)
    log.info("benchmark_complete", iterations=n, out=out_path)


def _write(results: dict[str, list[float]], n: int, out_path: str, context: str) -> None:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = ["| Operation | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) |",
            "| --- | --- | --- | --- | --- |"]
    for op, s in results.items():
        rows.append(f"| {op} | {_pctl(s,50):.2f} | {_pctl(s,95):.2f} | "
                    f"{_pctl(s,99):.2f} | {statistics.mean(s):.2f} |")
    table = "\n".join(rows)
    doc = f"""# Benchmarks

Latency of the CockroachDB memory operations the recovery guarantee depends on.
Reproduce with `make benchmark` (or `python scripts/benchmark.py --n {n}`) against
your own cluster — numbers vary with cluster tier, region, and client distance.

**Run:** {now} · **Iterations:** {n} · **Vector search:** deterministic synthetic
vectors (no Bedrock) · **Measured from:** {context}

{table}

Notes:
- `end-to-end resume` is the money metric: recovery read of the interrupted step
  plus re-running and committing it — the full cold-resume path a killed agent pays.
- `find_similar` is CockroachDB's C-SPANN ANN search (`service` filter + `<->` rank).
- Measured client-side (`time.perf_counter`) around each call, so it includes the
  round trip and commit, not just server execution.
- **These are measured from a developer machine, not the deployed Lambda.** Absolute
  latency is dominated by per-call connection setup (TLS + Serverless routing) over the
  public internet — each call opens a fresh connection, matching the Lambda's cold
  per-invocation pattern. The orchestrator Lambda is co-located with the cluster in
  eu-central-1 (ADR 007), so production per-call latency is expected to be substantially
  lower. Read the *relative* cost between operations (end-to-end resume ≈ 3× a single
  commit) as the durable signal, not the absolute milliseconds.
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50, help="iterations per operation")
    parser.add_argument("--out", default="docs/BENCHMARKS.md")
    parser.add_argument(
        "--context",
        default="developer workstation over the public internet -> CockroachDB Cloud "
                "free-tier (Serverless), eu-central-1; fresh connection per call",
        help="describe where the benchmark ran (client location, cluster tier/region)",
    )
    args = parser.parse_args()
    run(args.n, args.out, args.context)
