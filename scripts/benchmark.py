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
import base64
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
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
# The Lambda benchmark must target a service that HAS seeded embeddings, or the
# vector search returns nothing, propose_next_step short-circuits to
# page_on_call_engineer, and the Bedrock reasoning leg never executes — giving
# fast numbers for a path the real system doesn't take. `SERVICE` above is
# deliberately isolated for the CockroachDB benchmarks, which seed their own.
LAMBDA_BENCH_SERVICE = os.getenv("LAMBDA_BENCH_SERVICE", "checkout-api")
REGION = "eu-central-1"
_REPORT = re.compile(r"Duration:\s*([\d.]+) ms.*?Billed Duration:\s*(\d+) ms", re.S)
_INIT = re.compile(r"Init Duration:\s*([\d.]+) ms")
_MAXMEM = re.compile(r"Max Memory Used:\s*(\d+) MB")


def _invoke_lambda(client, payload: dict) -> tuple[float, dict]:
    """Invoke the deployed orchestrator and return (client round trip ms, the
    REPORT figures Lambda itself measured).

    Both numbers matter and mean different things: the client round trip is what
    a caller experiences from wherever it sits, while Lambda's own Duration is
    in-region and excludes network. Reporting only the first would confuse the
    co-location question this file exists to answer.
    """
    t = time.perf_counter()
    resp = client.invoke(
        FunctionName=settings.lambda_function_name,
        InvocationType="RequestResponse",
        LogType="Tail",
        Payload=json.dumps(payload).encode(),
    )
    round_trip = (time.perf_counter() - t) * 1000.0
    body = json.loads(resp["Payload"].read())
    tail = base64.b64decode(resp.get("LogResult", "")).decode("utf-8", "replace")

    figures: dict = {"result": body}
    if m := _REPORT.search(tail):
        figures["duration_ms"] = float(m.group(1))
    if m := _INIT.search(tail):
        figures["init_ms"] = float(m.group(1))
    if m := _MAXMEM.search(tail):
        figures["max_memory_mb"] = int(m.group(1))
    return round_trip, figures


def _bench_lambda(n: int) -> dict[str, list[float]]:
    """Drive the DEPLOYED function and time the two paths that matter.

    Each correlation_id is invoked twice: once to open the incident, once more
    so the second invocation must recover it from CockroachDB. That second
    number is the recovery guarantee's real cost on real infrastructure —
    everything else in this file is a proxy for it.
    """
    import boto3

    client = boto3.client("lambda", region_name=settings.aws_region)
    out: dict[str, list[float]] = {
        "invocation — new incident (client round trip)": [],
        "invocation — RESUMED from CockroachDB (client round trip)": [],
        "Lambda-reported Duration — new incident": [],
        "Lambda-reported Duration — resumed": [],
    }
    init_ms: list[float] = []
    correlation_ids: list[str] = []
    # Count what each invocation actually did rather than asserting it in prose.
    # The first version of this benchmark used a service with no seeded
    # embeddings, so find_similar returned nothing, propose_next_step
    # short-circuited to page_on_call_engineer, and Claude was never called —
    # while the generated doc claimed the timings included real reasoning.
    sources: dict[str, int] = {}

    for i in range(n):
        cid = f"bench-lambda-{uuid.uuid4().hex[:8]}-{i}"
        correlation_ids.append(cid)
        alert = {
            # LAMBDA_BENCH_SERVICE must be a service with seeded embeddings, or
            # the vector search finds no precedent and the Bedrock reasoning leg
            # never runs — which would silently benchmark a cheaper path.
            "correlation_id": cid,
            "service": LAMBDA_BENCH_SERVICE,
            "region": REGION,
            "severity": "high",
            "text": "checkout-api p99 latency 4200ms, connection pool saturated after deploy",
        }
        for label, dur_label in (
            ("invocation — new incident (client round trip)", "Lambda-reported Duration — new incident"),
            ("invocation — RESUMED from CockroachDB (client round trip)", "Lambda-reported Duration — resumed"),
        ):
            rt, fig = _invoke_lambda(client, alert)
            out[label].append(rt)
            if "duration_ms" in fig:
                out[dur_label].append(fig["duration_ms"])
            if "init_ms" in fig:
                init_ms.append(fig["init_ms"])
            res = fig["result"]
            key = f"{res.get('correlation_source')}/{res.get('reasoning_source')}"
            sources[key] = sources.get(key, 0) + 1

        assert fig["result"].get("resumed") is True, (
            f"second invocation did not resume — benchmark is not measuring the recovery path: {fig['result']}"
        )

    # Cold starts, measured deliberately rather than hoped for. Sequential calls
    # reuse a warm execution environment, so the loop above typically observes
    # zero Init Durations — which would quietly drop the one number ADR 002 is
    # about. Firing invocations CONCURRENTLY forces Lambda to provision separate
    # environments, so each pays init.
    cold_ids = [f"bench-cold-{uuid.uuid4().hex[:8]}-{i}" for i in range(n)]
    correlation_ids.extend(cold_ids)
    with cf.ThreadPoolExecutor(max_workers=n) as pool:
        futures = [
            pool.submit(
                _invoke_lambda,
                client,
                {
                    "correlation_id": cid,
                    "service": LAMBDA_BENCH_SERVICE,
                    "region": REGION,
                    "severity": "high",
                    "text": "checkout-api p99 latency 4200ms, connection pool saturated after deploy",
                },
            )
            for cid in cold_ids
        ]
        for fut in cf.as_completed(futures):
            _, fig = fut.result()
            if "init_ms" in fig:
                init_ms.append(fig["init_ms"])
            res = fig["result"]
            key = f"{res.get('correlation_source')}/{res.get('reasoning_source')}"
            sources[key] = sources.get(key, 0) + 1

    if init_ms:
        out["cold-start init (Lambda Init Duration)"] = init_ms
    out["__sources__"] = sources  # type: ignore[assignment]  # consumed by _write, not a latency series
    out["__cold_starts__"] = [len(init_ms), n * 3]  # type: ignore[assignment]

    # Clean up the incidents these invocations created; the demo cluster is
    # judge-facing and bench rows are noise in it.
    with psycopg.connect(settings.cockroach_database_url) as conn, conn.cursor() as cur:
        for cid in correlation_ids:
            cur.execute(
                "DELETE FROM remediation_steps WHERE incident_id IN "
                "(SELECT incident_id FROM incidents WHERE correlation_id = %s)",
                (cid,),
            )
            cur.execute(
                "DELETE FROM incident_embeddings WHERE incident_id IN "
                "(SELECT incident_id FROM incidents WHERE correlation_id = %s)",
                (cid,),
            )
            cur.execute("DELETE FROM incidents WHERE correlation_id = %s", (cid,))
        conn.commit()

    return {k: v for k, v in out.items() if v}


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


def run(n: int, out_path: str, context: str, with_bedrock: bool = False, lambda_n: int = 0) -> None:
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

    # The Bedrock embed is the one leg of a remediation step that is NOT
    # CockroachDB, so measuring it is how you know whether correlation latency
    # is dominated by the database or by the model endpoint. Off by default:
    # it costs real InvokeModel calls, and the quota is dynamic (ADR 008), so a
    # benchmark that requires it would fail for anyone whose account is clamped.
    if with_bedrock:
        alert = "checkout-api p99 latency 4200ms, connection pool saturated after deploy"
        results["Titan embed (Bedrock InvokeModel)"] = _bench(lambda: correlation.embed(alert), n)
        query_vec = correlation.embed(alert)
    else:
        query_vec = deterministic_embedding("benchmark query vector")

    results["recovery read (get_open_incident)"] = _bench(lambda: memory.get_open_incident(created[0][1]), n)
    results["vector search (find_similar, k=5)"] = _bench(lambda: correlation.find_similar(SERVICE, query_vec), n)

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

    lambda_results = _bench_lambda(lambda_n) if lambda_n else None

    _write(results, n, out_path, context, with_bedrock, lambda_results)
    log.info("benchmark_complete", iterations=n, lambda_iterations=lambda_n, out=out_path)


def _table(results: dict[str, list[float]]) -> str:
    rows = ["| Operation | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | n |", "| --- | --- | --- | --- | --- | --- |"]
    for op, s in results.items():
        rows.append(
            f"| {op} | {_pctl(s, 50):.1f} | {_pctl(s, 95):.1f} | "
            f"{_pctl(s, 99):.1f} | {statistics.mean(s):.1f} | {len(s)} |"
        )
    return "\n".join(rows)


def _write(
    results: dict[str, list[float]],
    n: int,
    out_path: str,
    context: str,
    with_bedrock: bool,
    lambda_results: dict[str, list[float]] | None,
) -> None:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    vec_note = (
        "real Amazon Titan Text Embeddings V2 vectors"
        if with_bedrock
        else "deterministic synthetic vectors (no Bedrock)"
    )

    lambda_section = ""
    if lambda_results:
        sources: dict = lambda_results.pop("__sources__", {})  # type: ignore[assignment]
        cold_n, total_n = lambda_results.pop("__cold_starts__", [0, 0])  # type: ignore[assignment]
        lam = _table(lambda_results)
        resumed = lambda_results.get("Lambda-reported Duration — resumed", [])
        fresh = lambda_results.get("Lambda-reported Duration — new incident", [])

        delta = ""
        if resumed and fresh:
            mr, mf = statistics.mean(resumed), statistics.mean(fresh)
            d = mf - mr
            # Spread across the samples themselves. A difference smaller than
            # that is noise, and reporting it as a finding would be dishonest
            # at these sample sizes — "resuming costs 2 ms" is not a result.
            spread = max(
                (max(resumed) - min(resumed)) if len(resumed) > 1 else 0.0,
                (max(fresh) - min(fresh)) if len(fresh) > 1 else 0.0,
            )
            if abs(d) < spread:
                delta = (
                    f"\n**Resuming an incident and opening a new one cost the same.** "
                    f"{mr:.0f} ms vs {mf:.0f} ms mean — a {abs(d):.0f} ms difference against "
                    f"{spread:.0f} ms of spread within the samples themselves, i.e. indistinguishable "
                    "at this sample size. The recovery read that makes a killed agent's memory "
                    "survivable does not show up as a cost on the hot path: durability is bought by "
                    "*where* the state lives, not by spending time re-establishing it.\n"
                )
            elif d > 0:
                delta = (
                    f"\n**Resuming is {d:.0f} ms _faster_ than opening a new incident** "
                    f"({mr:.0f} ms vs {mf:.0f} ms mean). The recovery path is not a tax at all: "
                    "a resuming invocation does one indexed read on `correlation_id`, where a "
                    "fresh one does that same read plus two writes (`open_incident`, then "
                    "`set_state`). Durability is bought by *where* the state lives, not by "
                    "spending extra time on the hot path.\n"
                )
            else:
                delta = (
                    f"\nResuming costs **{-d:.0f} ms more** than opening a new incident "
                    f"({mr:.0f} ms vs {mf:.0f} ms mean) — the price of the recovery read that "
                    "makes a killed agent's memory survivable.\n"
                )

        src_line = ""
        if sources:
            pairs = ", ".join(f"`{k}` ×{v}" for k, v in sorted(sources.items()))
            src_line = (
                f"- **What actually ran** (`correlation_source`/`reasoning_source`, counted not assumed): "
                f"{pairs}. A `no_precedent` reasoning source means the vector search found nothing and "
                "Claude was never called — those invocations measure a strictly cheaper path.\n"
            )

        cold_line = ""
        if total_n:
            cold_line = (
                f"- **{cold_n} of {total_n} invocations paid a cold start.** Sequential calls reuse a warm "
                "execution environment, so the paired invocations above mostly skip init; the cold-start "
                "row comes from a separate batch fired *concurrently*, which forces Lambda to provision "
                "separate environments. ADR 002's claim is that no invocation may *depend* on warm state "
                "— not that AWS never supplies one — so both numbers are real and neither is the whole "
                "picture. The recovery path is exercised identically either way, since the first thing "
                "every invocation does is read CockroachDB.\n"
            )

        lambda_section = f"""
## 2. On the deployed Lambda (the number that counts)

`continuum-orchestrator`, eu-central-1, in-region with the cluster, no provisioned
concurrency (ADR 002). Each `correlation_id` is invoked twice: once to open the
incident, once more so the second invocation *must* recover it from CockroachDB.

Every invocation includes a fixed `STEP_EXECUTION_SECONDS` sleep simulating the
remediation window `chaos_kill.py` strikes in — **subtract it to read the real work.**

{lam}
{delta}
- **client round trip** is measured from the invoking machine, so it carries public
  internet latency to the AWS API. **Lambda-reported Duration** is what the function
  itself billed, in-region. Compare the two to see the network cost, and compare
  Duration here against §3 to see what co-location buys.
{src_line}{cold_line}"""

    doc = f"""# Benchmarks

What a remediation step actually costs, measured — not modelled. Reproduce with
`make benchmark`; numbers vary with cluster tier, region and client distance.

**Run:** {now} · **Vector search:** {vec_note}

**Correctness under adversity — kill storms, exactly-once under contention,
concurrent-agent throughput and vector search at scale — is measured separately
in [`RESILIENCE.md`](RESILIENCE.md).** This file answers *how fast*; that one
answers *does it stay correct when things go wrong*, which is the claim the
project actually rests on.

## 1. What this measures, and why

Continuum's claim is that an agent can be killed mid-incident and resume from
CockroachDB. That claim is only interesting if the memory layer is fast enough that
durability isn't paid for in latency. These are the operations on that path:

| Leg | What it is | Where it runs |
| --- | --- | --- |
| recovery read | `get_open_incident` — the first thing every invocation does (ADR 002) | CockroachDB |
| Titan embed | alert text → 1024-dim vector | Amazon Bedrock |
| vector search | C-SPANN ANN over `incident_embeddings`, `service` filter + `<->` rank | CockroachDB |
| step-start / step-done | the two `SERIALIZABLE` checkpoints a kill lands between (ADR 009) | CockroachDB |
| end-to-end resume | recovery read + re-run + commit — what a killed agent pays | CockroachDB |
{lambda_section}
## 3. CockroachDB memory operations, from a developer workstation

**Iterations:** {n} · **Measured from:** {context}

{_table(results)}

- `end-to-end resume` is the money metric: recovery read of the interrupted step plus
  re-running and committing it.
- Measured client-side (`time.perf_counter`) around each call, so it includes the round
  trip and commit, not just server execution. Each call opens a fresh connection,
  matching the Lambda's cold per-invocation pattern.
- These absolute numbers are dominated by per-call TLS setup and Serverless routing over
  the public internet. Read the *relative* cost between operations as the durable signal,
  and §2 for what the same work costs in-region.

## Caveats worth stating plainly

- CockroachDB Basic (Serverless) scales to zero; a cluster that has been idle pays a
  routing cost on the first call that a provisioned cluster would not.
- Percentiles over {n} samples are indicative, not production SLO evidence.
- Bedrock quotas are dynamic and account-level (ADR 008). A throttled account degrades
  to deterministic fallbacks, which would make these numbers *faster* and less
  meaningful — the `reasoning_source` / `correlation_source` markers on every step are
  how you confirm a run actually exercised Bedrock.
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(_table(results))
    if lambda_results:
        print()
        print(_table(lambda_results))


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
    parser.add_argument(
        "--with-bedrock",
        action="store_true",
        help="measure real Titan embed latency and search with real vectors (costs InvokeModel calls)",
    )
    parser.add_argument(
        "--lambda-n",
        type=int,
        default=0,
        help="also drive the DEPLOYED orchestrator this many times (each runs twice: open, then resume). "
        "Needs lambda:InvokeFunction — e.g. AWS_PROFILE=continuum-admin",
    )
    args = parser.parse_args()
    run(args.n, args.out, args.context, args.with_bedrock, args.lambda_n)
