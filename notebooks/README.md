# Notebooks

| Notebook | Purpose |
| --- | --- |
| [`DEMO_RUNBOOK.ipynb`](DEMO_RUNBOOK.ipynb) | Interactive walkthrough of the kill-and-recover sequence against a running Continuum API |
| [`DEMO_RUNBOOK.results.ipynb`](DEMO_RUNBOOK.results.ipynb) | Frozen, Markdown-only record of a completed run — see below |

## Why this exists

The recovery guarantee is easy to *assert* and hard to *believe* without watching it. This notebook
lets a reviewer step through the sequence themselves — fire a synthetic alert, watch the step
commit, kill the process, then see the row sitting in `executing` in CockroachDB with nothing alive
to own it, and finally watch a cold start resume that exact step.

It is a companion to, not a replacement for, the recording script in
[`submission/DEMO_SCRIPT.md`](../submission/DEMO_SCRIPT.md), which owns the beat structure and
timings for the demo video.

## Running it

```bash
pip install -r ../requirements.txt   # httpx + psycopg are all the notebook needs
pip install jupyterlab               # not a project dependency — install ad hoc
make run-api                         # from the repo root, in a separate terminal
                                     # Windows: python -m uvicorn api.main:app --port 8000
jupyter lab notebooks/DEMO_RUNBOOK.ipynb
```

Set `BASE_URL` in the first code cell. Sections that query CockroachDB directly also need
`COCKROACH_DATABASE_URL` in the environment.

## What needs a local API

| Section | Local API required? |
| --- | --- |
| 1–3 (alert, MCP read, step advance) | No — works against any reachable deployment |
| 4–5 (the kill, confirming durable `executing`) | **Yes** — `chaos_kill.py` kills a process by port |

## Rendered snapshot

[`DEMO_RUNBOOK.results.ipynb`](DEMO_RUNBOOK.results.ipynb) is a frozen, Markdown-only record of a
completed kill-and-recover run — no executable cells, no connection details, just the real
captured output (incident IDs, timestamps, the durable `executing` row and its `detail` JSONB, the
resumed/re-executed step). `DEMO_RUNBOOK.ipynb` above is the clean, output-free template to run
yourself; create a new results record only from a completed run against a live API and cluster.

Two properties make it evidence rather than a write-up, and both are worth preserving if it is
ever regenerated:

- **Every block is interpolated from the run's captured transcript, never retyped.** A hand-typed
  record drifts from what actually happened, and the drift is invisible. The one value in the
  current record that *was* hand-derived rendered "27s later, inside the 5s window" — arithmetic
  that contradicts itself in the same sentence — which is exactly the failure mode.
- **It states what the run does not show.** This capture drove the local API, so its steps record
  `runtime: local` and it cannot speak to Lambda; the deployed-runtime evidence lives under
  [`../assets/deploy-restart-run/`](../assets/deploy-restart-run/). A record that only lists wins
  reads as marketing.

## Conventions

- **Read-only against incident state, except through the API.** The notebook never writes to
  `incidents` or `remediation_steps` directly — `agents/memory_agent.py` is the only write path,
  and that property is load-bearing (ADR 001/003). Direct `psycopg` use here is `SELECT` only.
- **Commit without outputs.** Cell outputs contain incident IDs and connection details from
  whatever cluster it was run against. Clear them before committing:
  `jupyter nbconvert --clear-output --inplace notebooks/DEMO_RUNBOOK.ipynb`
- **Ruff lints notebooks.** `make lint` covers `.ipynb` files, so imports go at the top of their
  cell and the usual rules apply.
- **Section 4's kill and section 6's resume must target the SAME incident this notebook opened.**
  Pass `--correlation-id <CORRELATION_ID from cell 1>` to `scripts/demo_run.py` in both — without
  it, `demo_run.py` drives its own separate incident (its fixed default or a fresh `--new` one),
  and section 5's `INCIDENT_ID`-scoped query can never show the kill that actually happened.
  `--correlation-id` and `--new` are mutually exclusive, so passing both is an error rather than a
  silent no-op.
- **The notebook's alert body mirrors `DEMO_ALERT` in `scripts/demo_run.py`.** Sections 4 and 6
  advance the incident using that script, and the orchestrator re-proposes from the alert text on
  every tick — so if the two bodies diverge, the incident is opened by one alert and resumed by
  another. Change one, change both. The shared text is also the one whose precedent distance
  (≈0.7902 against the committed Titan fixture) is measured and documented.
