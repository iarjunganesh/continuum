"""
A local single-node CockroachDB, for the work that should never touch the Cloud cluster.

The Cloud cluster is shared infrastructure: the public demo Space reads it, the
deployed Lambda writes to it, and its Request Unit allowance is finite and
monthly. On 2026-08-03 the resilience benchmark suites consumed the whole
allowance, which disabled the cluster and took the demo down with it — the load
harness broke the thing it was measuring.

This is the fix, and it is the same recipe CI already uses (`.github/workflows/
ci.yml`), so the integration suite and the vector-index test are known to pass
against it: one container, `--insecure`, vector indexing enabled, `infra/
schema.sql` applied.

What it is good for: the integration suite, `chaos_capture.py`, seeding
experiments, and any benchmark whose result is a *correctness count* — resumed,
duplicated, lost, violations. Those are absolute and hold anywhere.

What it is not good for: latency figures published as CockroachDB Cloud numbers.
A single insecure node on the same machine has no network, no replication and no
RU accounting. Measure timings against the real cluster, deliberately, at the
documented default sizes.

Usage:
    python scripts/local_cluster.py up        # start, apply schema, print the URL
    python scripts/local_cluster.py down      # stop and remove
    python scripts/local_cluster.py status    # is it up, and does it have the schema
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CONTAINER = "continuum-crdb"
# Pinned to the version CI runs, so "passes locally" and "passes in CI" mean the
# same thing. Bump both together or neither.
IMAGE = "cockroachdb/cockroach:latest-v25.2"
SQL_PORT = 26257
CONSOLE_PORT = 8080
URL = f"postgresql://root@localhost:{SQL_PORT}/defaultdb?sslmode=disable"


def _run(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, **kw)


def _docker_ok() -> bool:
    probe = _run(["docker", "info"])
    if probe.returncode == 0:
        return True
    print("Docker is installed but the daemon is not reachable — start Docker Desktop.", file=sys.stderr)
    return False


def _sql(stmt: str) -> subprocess.CompletedProcess:
    return _run(["docker", "exec", CONTAINER, "./cockroach", "sql", "--insecure", "-e", stmt])


def up() -> int:
    if not _docker_ok():
        return 1

    existing = _run(["docker", "ps", "-aq", "-f", f"name=^{CONTAINER}$"]).stdout.strip()
    if existing:
        print(f"removing existing container {CONTAINER}")
        _run(["docker", "rm", "-f", CONTAINER])

    print(f"starting {IMAGE} as {CONTAINER}")
    started = _run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER,
            "-p",
            f"{SQL_PORT}:26257",
            "-p",
            f"{CONSOLE_PORT}:8080",
            IMAGE,
            "start-single-node",
            "--insecure",
        ]
    )
    if started.returncode != 0:
        print(started.stderr.strip(), file=sys.stderr)
        return 1

    # The container reports healthy before SQL accepts connections; poll the way
    # CI does rather than sleeping a guessed interval.
    for _ in range(60):
        if _sql("SELECT 1").returncode == 0:
            break
        time.sleep(1)
    else:
        print("cluster did not accept SQL within 60s", file=sys.stderr)
        return 1

    # Vector indexing is off by default in this version; the C-SPANN index in
    # infra/schema.sql fails to create without it, and the failure reads as a
    # syntax error rather than a missing feature.
    vec = _sql("SET CLUSTER SETTING feature.vector_index.enabled = true;")
    if vec.returncode != 0:
        print(vec.stderr.strip(), file=sys.stderr)
        return 1

    schema = (REPO_ROOT / "infra" / "schema.sql").read_text(encoding="utf-8")
    applied = _run(
        ["docker", "exec", "-i", CONTAINER, "./cockroach", "sql", "--insecure"],
        input=schema,
    )
    if applied.returncode != 0:
        print(applied.stderr.strip(), file=sys.stderr)
        return 1

    print(
        f"\nready. schema applied, vector indexing on.\n"
        f"  DB console : http://localhost:{CONSOLE_PORT}\n"
        f"  connect    : {URL}\n\n"
        f"Point this shell at it:\n"
        f"  export COCKROACH_DATABASE_URL='{URL}'      # bash\n"
        f'  $env:COCKROACH_DATABASE_URL = "{URL}"      # powershell\n\n'
        f"Then seed it: python scripts/seed_memory.py --file data/synthetic/incidents_seed.jsonl "
        f"--no-embeddings\n"
        f"or restore the real memory: python scripts/restore_memory.py --file "
        f"data/snapshots/memory-20260802-2215.jsonl"
    )
    return 0


def down() -> int:
    if not _docker_ok():
        return 1
    result = _run(["docker", "rm", "-f", CONTAINER])
    print(f"removed {CONTAINER}" if result.returncode == 0 else result.stderr.strip())
    return 0


def status() -> int:
    if not _docker_ok():
        return 1
    running = _run(["docker", "ps", "-q", "-f", f"name=^{CONTAINER}$"]).stdout.strip()
    if not running:
        print(f"{CONTAINER}: not running")
        return 1
    tables = _sql("SELECT count(*) FROM [SHOW TABLES];")
    print(f"{CONTAINER}: running at {URL}")
    print(f"tables: {tables.stdout.strip().splitlines()[-1] if tables.returncode == 0 else 'schema not applied'}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["up", "down", "status"])
    args = p.parse_args()
    raise SystemExit({"up": up, "down": down, "status": status}[args.action]())


if __name__ == "__main__":
    main()
