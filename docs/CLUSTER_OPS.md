# CockroachDB Cluster Operations

How to run things against the CockroachDB Cloud cluster without taking the demo down.

This exists because the cluster has been unavailable twice, for two different reasons, and both
were avoidable. It is the operational counterpart to [`../submission/COSTS.md`](../submission/COSTS.md)
— that document explains what things cost, this one says what to run and where.

**The one-line rule: the Cloud cluster serves the demo, and nothing else.** Benchmarks, chaos
captures and the integration suite go to `make local-cluster`.

---

## The budget you are working inside

| | Value |
| --- | --- |
| Free allowance | **$15/month → 50M Request Units + 10 GiB storage**, resets monthly |
| Cluster limits set | **100M RU/mo**, **10 GiB/mo** |
| Gross ceiling shown in console | **$25.00/mo** (100M × $0.20/M + 10 GiB × $0.50/GiB) |
| Net worst case after the free credit | **≈ $10/mo ≈ 105 SEK** |
| Measured lifetime usage (to 2026-08-03) | **3.42M RU, 19.51 MiB** |

So normal operation uses about **7% of one month's free allowance**, and the cap exists only to
bound an accident. Two consequences worth internalising:

- **You are not close to the money.** Do not skip a demo rehearsal to save Request Units.
- **Hitting the RU limit disables the cluster** until you raise it or the billing cycle rolls
  over. It is a kill switch, not a warning. That is why the cap is set at 2× the free allowance
  rather than exactly at it — a cap that trips during judging costs far more than $10 does.

Organization Admins get email at **50% / 75% / 100%** of the limit. At a 100M cap the 50% alert
fires exactly when you leave the free tier. **Treat that email as the signal to stop and look**,
not as routine.

## Two ways to lose the cluster, and only one is visible in your metrics

| | What it looks like | What actually happened |
| --- | --- | --- |
| **The meter** | Cluster disabled, error names a Request Unit limit | You spent the allowance |
| **The clock** | Cluster disabled, error names a Request Unit limit | An entitlement expired |

They are indistinguishable from the error message. On 2026-08-03 this project hit the *clock* — a
30-day trial lapsed with **$399 of $400 credits and 99.1% of the RU allowance unspent** — and the
error text caused it to be diagnosed as the meter for three days. Console screenshots are in
[`../assets/provider-evidence/`](../assets/provider-evidence/).

**Before diagnosing a disabled cluster as overuse, read the billing page.** Usage dashboards, RU
guards and budget alerts all watch consumption. Nothing watches an expiry date.

---

## Where each command belongs

### Safe on the Cloud cluster

These are what the demo is made of. Their cost is negligible — the whole incident path is three
`SERIALIZABLE` transaction pairs and one vector search.

| Command | Notes |
| --- | --- |
| `make migrate` | Schema only. Idempotent |
| `make seed-data-offline` | ~40 incidents, deterministic vectors, zero AWS calls. Cheap. Prefer over `seed-data` |
| `make seed-data` | Same, but calls Bedrock for real Titan vectors. Costs AWS, not RU |
| `make demo` | One remediation tick |
| `make chaos-demo` | The kill-and-recover sequence. This is the graded flow — rehearse it freely |
| `make run-ui` | See the Space discipline section below |
| `make export-memory` | Read-only snapshot. Run before anything risky |
| `make restore-memory` | `ON CONFLICT DO NOTHING`, so it never overwrites or deletes |

### Must go to the local cluster

`make local-cluster` — the same single-node container CI uses, schema applied, vector indexing on.

| Command | Why it does not belong on Cloud |
| --- | --- |
| `make resilience-bench` | Each sample is a full incident with real writes. The N=200 run left **665 incidents and 1,353 steps** on the demo cluster, 431 of them frozen mid-run |
| `make benchmark` | Seeds up to 10,000 vectors to measure the index at scale |
| `pytest tests/integration` | Writes real incidents through the real schema, by design |
| `make chaos-capture` | Deliberately leaves its incident in the cluster and prints the id |
| `make load-test` | k6 read-path smoke. Read-only, but sustained and unbounded |

Two of these have guards as of 0.9.2: `resilience_bench.py` refuses more than 400 incidents or
10,000 vectors against a `*.cockroachlabs.cloud` host without `--allow-cloud-burn`. **The guard is
a backstop, not permission** — pointing a bench at Cloud is still the wrong call even under the
limit, because the cost is demo-cleanliness, not Request Units.

**The one exception:** published *latency* numbers must come from the real Cloud cluster —
network path, TLS handshake and multi-region replication are the thing being measured, and a
local container does not have them. Correctness counts (exactly-once, resume-after-kill) hold
anywhere and belong local. `scripts/local_cluster.py` says this in its docstring too.

---

## Hugging Face Space discipline

The Space is a judge-facing surface pointed at the same cluster. It is the single largest
uncontrolled RU consumer in the system.

- **Never set `CONTINUUM_UI_REFRESH_SECONDS` on the Space.** The 5s timer was measured at ~50 RU
  per refresh — **~36K RU/hour, per open browser tab.** One forgotten tab left open for a
  four-week judging period is ≈ **24M RU, about half the monthly free allowance**, from nobody
  doing anything.
- Manual refresh and no-load-on-open are the defaults (`CONTINUUM_UI_LOAD_ON_OPEN=0`). If you
  enable the timer to record the demo, **unset it the same day.** Set a reminder; this has already
  gone wrong once.
- **Do not leave the Space open in a background tab while working.** A refresh you did not intend
  is still a refresh.
- Put the demo URL in the submission form's judge-only **Additional Info** field, per the
  organizers' guidance in Devpost forum threads #44284 and #44317. It keeps public traffic off the
  cluster as a side effect.
- Secrets are only re-read on Space **restart**. Changing `COCKROACH_DATABASE_URL` without a
  restart silently keeps the old value.

## Keeping the demo readable

Judges see open incidents. Anything left in a non-terminal state is visible and is read as the
system's current condition — which matters more here than usual, because a wall of permanently
stuck rows argues against the exact claim being graded.

Check before any capture or submission:

```bash
python - <<'PY'
import psycopg
from config import settings
with psycopg.connect(settings.cockroach_database_url) as c, c.cursor() as cur:
    cur.execute("SELECT service, state, count(*) FROM incidents GROUP BY 1,2 ORDER BY 3 DESC")
    for row in cur.fetchall():
        print(row)
PY
```

Anything from `resilience-bench` or a test service on the demo cluster is residue. Remove it —
scoped to the offending service, never a bare `DELETE FROM incidents`:

```sql
DELETE FROM remediation_steps WHERE incident_id IN (
    SELECT incident_id FROM incidents WHERE service = 'resilience-bench'
);
DELETE FROM incidents WHERE service = 'resilience-bench';
```

This is a **maintenance** operation and a deliberate, one-off exception to the single-write-path
rule in `CLAUDE.md` — it is not application behaviour and must never be wired into an agent.
Snapshot first (`make export-memory`), and scope by `service`, so a mistake cannot reach the
seeded demo incidents.

## Pre-demo checklist

1. `make export-memory` — snapshot before you touch anything
2. Confirm the cluster is `AVAILABLE` and check the RU gauge on the Cluster Overview
3. Confirm **Deletion protection** is on
4. `make probe-bedrock` — quotas are dynamic; a throttled account degrades *silently* to fallbacks
5. Check the incident-state breakdown above; purge residue
6. Verify the vector index still plans correctly — `EXPLAIN` should show `• vector search`, never
   `spans: FULL SCAN` (see `tests/integration/test_vector_index.py`)
7. Rehearse `make chaos-demo` — cheap, do it as often as you like
8. Afterwards: confirm no refresh timer is set on the Space

## If the cluster is disabled

1. **Read the billing page before assuming overuse.** Check credits remaining and RU used against
   the limit. If usage is low, it is the clock — an expiry or a lapsed payment method, not a
   workload
2. If it is genuinely the meter: raise the limit, or wait for the billing cycle to roll over
3. The data is snapshot-covered — `data/snapshots/*.jsonl`, restored by
   `make restore-memory SNAPSHOT=…`, round-tripped by `tests/integration/test_snapshot_roundtrip.py`
4. Standing up a fresh cluster means re-pointing `.env`, the Space secrets **and** the Lambda
   environment, and re-granting the MCP service account the **Cluster Operator** role. Prefer
   fixing the existing cluster — it keeps the cluster id that `assets/provider-evidence/` shows
