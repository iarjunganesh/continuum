# Notebooks

| Notebook | Purpose |
| --- | --- |
| [`DEMO_RUNBOOK.ipynb`](DEMO_RUNBOOK.ipynb) | Interactive walkthrough of the kill-and-recover sequence against a running Continuum API |

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

## Conventions

- **Read-only against incident state, except through the API.** The notebook never writes to
  `incidents` or `remediation_steps` directly — `agents/memory_agent.py` is the only write path,
  and that property is load-bearing (ADR 001/003). Direct `psycopg` use here is `SELECT` only.
- **Commit without outputs.** Cell outputs contain incident IDs and connection details from
  whatever cluster it was run against. Clear them before committing:
  `jupyter nbconvert --clear-output --inplace notebooks/DEMO_RUNBOOK.ipynb`
- **Ruff lints notebooks.** `make lint` covers `.ipynb` files, so imports go at the top of their
  cell and the usual rules apply.
