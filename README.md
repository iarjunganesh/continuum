---
title: Continuum
emoji: 🔁
colorFrom: purple
colorTo: blue
sdk: gradio
sdk_version: 6.22.0
python_version: "3.14"
app_file: ui/app.py
pinned: false
license: mit
---

# Continuum

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/demo-cards/banner-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/demo-cards/banner-light.svg">
    <!-- ⬇ banner size — change this one width -->
    <img width="620" src="assets/demo-cards/banner-light.svg"
         alt="Continuum — memory that outlives the failure. · CockroachDB × AWS Hackathon 2026"/>
  </picture>
</p>

<p align="center">
  <strong>An autonomous incident-response agent that resumes the exact step it was killed on — because its memory lives in CockroachDB, not in the process.</strong>
</p>

> **CockroachDB × AWS Hackathon 2026 — Build with Agentic Memory**

[![CI](https://github.com/iarjunganesh/continuum/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/iarjunganesh/continuum/actions/workflows/ci.yml)
[![Codecov](https://codecov.io/gh/iarjunganesh/continuum/graph/badge.svg)](https://codecov.io/gh/iarjunganesh/continuum)
[![Release](https://img.shields.io/badge/release-latest-2ea44f?logo=github&logoColor=white)](https://github.com/iarjunganesh/continuum/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Watch Video](https://img.shields.io/badge/%E2%96%B6_Watch-3--min_demo-FF0000?logo=youtube&logoColor=white)

<!-- Row 2 — AWS services -->
[![AWS Lambda](https://img.shields.io/badge/AWS_Lambda-python3.14-FF9900?logo=awslambda&logoColor=white)](https://aws.amazon.com/lambda/)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon_Bedrock-Titan_Embed_v2-FF9900?logo=amazonwebservices&logoColor=white)](https://aws.amazon.com/bedrock/)
[![Claude on Bedrock](https://img.shields.io/badge/Bedrock-Claude_Sonnet_4.5-FF9900?logo=amazonwebservices&logoColor=white)](https://aws.amazon.com/bedrock/)
[![AWS SAM](https://img.shields.io/badge/AWS_SAM-infrastructure_as_code-FF9900?logo=amazonwebservices&logoColor=white)](https://aws.amazon.com/serverless/sam/)
[![AWS IAM](https://img.shields.io/badge/AWS_IAM-least_privilege-FF9900?logo=amazonwebservices&logoColor=white)](https://aws.amazon.com/iam/)

<!-- Row 3 — CockroachDB -->
[![CockroachDB Cloud](https://img.shields.io/badge/CockroachDB_Cloud-source_of_truth-6933FF?logo=cockroachlabs&logoColor=white)](https://www.cockroachlabs.com/docs/cockroachcloud/)
[![Distributed Vector Indexing](https://img.shields.io/badge/Distributed_Vector_Indexing-C--SPANN_1024d-6933FF?logo=cockroachlabs&logoColor=white)](https://www.cockroachlabs.com/docs/stable/vector-indexes)
[![Managed MCP Server](https://img.shields.io/badge/Managed_MCP_Server-read--only-6933FF?logo=cockroachlabs&logoColor=white)](https://www.cockroachlabs.com/docs/stable/cockroachdb-and-ai)
[![SERIALIZABLE](https://img.shields.io/badge/Isolation-SERIALIZABLE-6933FF?logo=cockroachlabs&logoColor=white)](https://www.cockroachlabs.com/docs/stable/demo-serializable)

<!-- Row 4 — Python stack -->
[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![psycopg](https://img.shields.io/badge/psycopg-3.3-336791?logo=postgresql&logoColor=white)](https://www.psycopg.org/psycopg3/)
[![Pydantic](https://img.shields.io/badge/Pydantic-2.12_models-E92063?logo=pydantic&logoColor=white)](https://pydantic.dev/)
[![structlog](https://img.shields.io/badge/structlog-JSON_observability-4A90E2)](https://www.structlog.org/)
[![Ruff](https://img.shields.io/badge/Ruff-lint%20%2B%20format-D7FF64?logo=ruff&logoColor=111827)](https://docs.astral.sh/ruff/)
[![Mypy](https://img.shields.io/badge/Mypy-type_checked-2A6DB2?logo=python&logoColor=white)](https://mypy-lang.org/)
[![pytest](https://img.shields.io/badge/pytest-9.1-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)

<!-- Row 5 — Demo UI -->
[![Gradio](https://img.shields.io/badge/Gradio-6.22-F97316?logo=gradio&logoColor=white)](https://gradio.app/)
[![Hugging Face Spaces](https://img.shields.io/badge/🤗_Hugging_Face-Spaces-FFD21E)](https://huggingface.co/spaces)
[![Jupyter](https://img.shields.io/badge/Demo-Jupyter%20Notebook-F37626?logo=jupyter&logoColor=white)](notebooks/DEMO_RUNBOOK.ipynb)

<!-- Row 6 — Hosting (live deployment) -->
[![HF Spaces live demo](https://img.shields.io/badge/🤗_HF_Spaces-live_demo-FFD21E)](https://huggingface.co/spaces/iarjunganesh/continuum)

---

## What Is This?

Most "agent memory" demos store chat history. Continuum stores something that matters under pressure: **which remediation step is executing right now, which alert correlates with which past incident, and the exact state of recovery the instant before something crashes.**

Every state transition is committed to **CockroachDB** before and after it happens. Kill the process mid-step — no graceful shutdown, no checkpoint call — and the next cold invocation reads the durable state, sees a step frozen in `executing`, and resumes *that exact step*. No lost context, no duplicated work, no human re-input.

**All incident and alert data is synthetic.** No real production systems, credentials, or customer data.

---

## The Problem

The conditions that cause production incidents — resource exhaustion, node failure, deploy rollbacks, autoscaling churn — are exactly the conditions that kill the agent responding to them. An agent holding its working state in process memory doesn't degrade gracefully when that happens. It stops, and a human restarts the incident from zero, without knowing which actions already ran.

That makes "did this step already execute?" the most expensive question in an incident: re-running a remediation action can be worse than not running it at all.

> **The agent's execution environment is allowed to die mid-incident. Its memory is not.**

Continuum treats that as a design constraint rather than an edge case. The recovery path is not error handling bolted onto a happy path — it is the *only* path, exercised on every single invocation.

---

## How It Works

1. A **synthetic alert** fires (latency spike, error-rate breach, connection saturation)
2. The **Orchestrator** (AWS Lambda) does the same thing whether its execution environment is brand new or reused — its *first action, always*, is a CockroachDB recovery read for open incident state matching this alert
3. The **Correlation Agent** embeds the alert via **Amazon Bedrock** (Titan v2, 1024-dim) and queries CockroachDB's **C-SPANN vector index** for semantically similar past incidents — structured filters and semantic ranking in one SQL round trip
4. The **Remediation Agent** reasons over the matched precedent (Claude on Bedrock) and proposes the next step
5. The **Memory Agent** — the *only* module allowed to write state — commits each step in explicit `SERIALIZABLE` transactions: the proposed action and `executing` status together (a forward step is claimed exactly once, `ON CONFLICT DO NOTHING`), then `executed`, with `resolved` committed atomically alongside the final step
6. **`chaos_kill.py`** hard-kills the process mid-execution; the step stays durably `executing` in CockroachDB — the fingerprint the next invocation resumes from
7. The **Query Agent** answers live questions through the **CockroachDB Cloud Managed MCP Server** — *"show me all open incidents and their current remediation step"* — from `GET /api/v1/incidents/open` and the Gradio UI's "Ask via MCP" button, not just from a human typing into an IDE

---

## Architecture

<p align="center">
  <a href="assets/architecture/architecture-diagram-light.svg" target="_blank" rel="noopener noreferrer">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/architecture/architecture-diagram-dark.svg">
      <source media="(prefers-color-scheme: light)" srcset="assets/architecture/architecture-diagram-light.svg">
      <img width="900" src="assets/architecture/architecture-diagram-light.svg"
           alt="Continuum architecture — a synthetic alert enters a stateless AWS Lambda whose Orchestrator performs a CockroachDB recovery read first; the Correlation, Remediation, Memory and Query agents run inside it, with Bedrock providing Titan embeddings and Claude reasoning as best-effort side calls. The Memory Agent commits every step to CockroachDB Cloud under SERIALIZABLE isolation, correlation runs ANN search against a VECTOR(1024) C-SPANN index, and the Query Agent reads live state through the Managed MCP Server. chaos_kill.py hard-kills the Lambda mid-step, and the durable state is what the next cold invocation resumes from."/>
    </picture>
  </a>
</p>

<sub>Click to enlarge (opens the full-resolution SVG — scales without pixelation): <a href="assets/architecture/architecture-diagram-light.svg" target="_blank" rel="noopener noreferrer">light</a> / <a href="assets/architecture/architecture-diagram-dark.svg" target="_blank" rel="noopener noreferrer">dark</a> · Source: <a href="assets/architecture/architecture-diagram.mmd">architecture-diagram.mmd</a> — rendered to brand-themed SVG/PNG (dark + light, plus 16:9 video cards) via <code>mermaid-cli</code>; see <a href="assets/architecture/README.md">assets/architecture/README.md</a> for the regenerate command.</sub>

**In short:** one invocation = one remediation step. The recovery read happens *before* any reasoning, every step commits in **two** `SERIALIZABLE` transactions with the execution window between them, and a forward step is claimed exactly once. The red path is the whole point — `chaos_kill.py` severs the process mid-step, and nothing about the recovery depends on that process ever coming back.

### The Recovery Pipeline

The component diagram shows *what* talks to what. This shows *what survives* — two cold Lambda invocations, no shared memory between them, handing off entirely through durable CockroachDB state:

<p align="center">
  <a href="assets/architecture/recovery-sequence-light.svg" target="_blank" rel="noopener noreferrer">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/architecture/recovery-sequence-dark.svg">
      <source media="(prefers-color-scheme: light)" srcset="assets/architecture/recovery-sequence-light.svg">
      <img width="820" src="assets/architecture/recovery-sequence-light.svg"
           alt="Recovery sequence — Lambda A receives an alert, performs a recovery read finding no open incident, opens one and commits step 0 as 'executing' in a SERIALIZABLE transaction before executing it. chaos_kill.py sends SIGKILL mid-execution with no graceful shutdown; the process is gone but step 0 remains durably 'executing' in CockroachDB. On the next tick a cold Lambda B performs its own recovery read first, finds step 0 still 'executing', re-runs that exact step rather than skipping or duplicating it, and commits it 'executed' — exactly-once preserved, state outlived the process."/>
    </picture>
  </a>
</p>

<sub>Click to enlarge: <a href="assets/architecture/recovery-sequence-light.svg" target="_blank" rel="noopener noreferrer">light</a> / <a href="assets/architecture/recovery-sequence-dark.svg" target="_blank" rel="noopener noreferrer">dark</a> · Source: <a href="assets/architecture/recovery-sequence.mmd">recovery-sequence.mmd</a></sub>

**Step 2 is the one that matters.** The recovery read is the *first* branch in `orchestrator.py`, before any new reasoning happens — not an error handler, not a retry wrapper. That is what separates Continuum from an agent that also happens to log to a database.

> **Deep dive** → **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — the dual memory model, the step-by-step recovery walkthrough, the vector-index DDL, and a typical-agent vs Continuum comparison.

### Architecture Decision Records

Ten decisions documented (001–010), **all accepted and implemented** — see [`docs/adr/`](docs/adr/) for full rationale.

| ADR | Decision |
| --- | --- |
| [001](docs/adr/001-dual-memory-model.md) | Dual transactional + vector memory in one CockroachDB store — no separate vector DB to drift |
| [002](docs/adr/002-stateless-lambda-recovery.md) | Stateless Lambda, no provisioned concurrency — every invocation must recover cold |
| [003](docs/adr/003-mcp-readonly-queries.md) | MCP Server in read-only mode as the live query interface |
| [004](docs/adr/004-ccloud-cli-audit-role.md) | ccloud CLI evaluated, then cut — 2 tools done well beats 3 done thin |
| [005](docs/adr/005-synthetic-incident-data.md) | Synthetic incident corpus only — no real infra, ever |
| [006](docs/adr/006-scope-cuts.md) | Explicit scope cuts, documented instead of hidden |
| [007](docs/adr/007-eu-central-1-region.md) | eu-central-1 deployment region, kept in sync across config/template/ADR |
| [008](docs/adr/008-bedrock-region-split.md) | Bedrock calls target their own `BEDROCK_REGION` setting rather than reusing `AWS_REGION`, so Bedrock can move without redeploying the Lambda — introduced when a dynamic account-level quota clamp probed as ~0 across all regions and models (lifted 2026-08-01); the default is back to eu-central-1 alongside the Lambda and cluster (addendum 3), and the app degrades to deterministic fallbacks either way |
| [009](docs/adr/009-step-execution-semantics.md) | Each step runs in two explicit `SERIALIZABLE` transactions with a forward-step claim (`ON CONFLICT DO NOTHING`) for exactly-once; correlation/Bedrock is best-effort, off the recovery critical path |
| [010](docs/adr/010-deploy-on-tag-from-ci.md) | The orchestrator deploys from CI on a `v*.*.*` tag — via GitHub OIDC, never stored AWS keys — so the deployed function and the newest tag cannot drift. Tags only, never pushes to `main`: redeploying during ordinary work would swap the code out from under a demo recording |

---

## CockroachDB Tools Used — and what the agent actually does with them

Two tools, both load-bearing in the running application (see ADR 004's resolution on why that's two done well rather than three done thin):

- **Distributed Vector Indexing** — `incident_embeddings.embedding VECTOR(1024)` with a C-SPANN index prefixed by `service`, so ANN search partitions per-service. The Correlation Agent's live query filters by structured columns *and* ranks by `<->` distance in one round trip. See [`infra/schema.sql`](infra/schema.sql).
- **CockroachDB Cloud Managed MCP Server** — read-only mode; `agents/query_agent.py` is a real MCP client (official `mcp` SDK, streamable HTTP) that the app itself calls from `GET /api/v1/incidents/open` and the Gradio UI's "Ask via MCP" button — not only a development convenience. The server's audit log doubles as a trail of what the agent looked at.

## AWS Services Used

- **AWS Lambda** — orchestrator execution on the `python3.14` runtime; deliberately **no provisioned concurrency**, so every invocation proves state comes from CockroachDB, not warm process memory (ADR 002)
- **Amazon Bedrock** — Titan Text Embeddings V2 for alert→vector; Claude Sonnet 4.5 for remediation reasoning over matched precedent (with a deterministic precedent-replay fallback so the control flow demos even when throttled)
- **AWS SAM** — infrastructure as code ([`infra/template.yaml`](infra/template.yaml)); the *absence* of `ProvisionedConcurrencyConfig` is a reviewable artifact rather than a console setting
- **AWS IAM** — least privilege: application credentials are scoped to Bedrock model invocation only and cannot list, create, or delete AWS resources

Judging-criteria mapping and full submission narrative: [`submission/DEVPOST.md`](submission/DEVPOST.md)

---

## Tech Stack

| Layer | Technology | Role |
| --- | --- | --- |
| **Memory** | [![CockroachDB Cloud](https://img.shields.io/badge/CockroachDB_Cloud-source_of_truth-6933FF?logo=cockroachlabs&logoColor=white)](https://www.cockroachlabs.com/docs/cockroachcloud/) | The durable record. Transactional incident state *and* vector embeddings in one store — no second database to drift (ADR 001) |
| **Durability** | [![SERIALIZABLE](https://img.shields.io/badge/Isolation-SERIALIZABLE-6933FF?logo=cockroachlabs&logoColor=white)](https://www.cockroachlabs.com/docs/stable/demo-serializable) | Two explicit transactions per step — `executing` committed *before* the execution window, `executed` after. A kill lands with `executing` durable (ADR 009) |
| **Correlation** | [![Vector Index](https://img.shields.io/badge/Vector_Index-C--SPANN_1024d-6933FF?logo=cockroachlabs&logoColor=white)](https://www.cockroachlabs.com/docs/stable/vector-indexes) | `service`-prefixed C-SPANN index; structured filter + `<->` ANN ranking in one round trip ([`infra/schema.sql`](infra/schema.sql)) |
| **Live Queries** | [![Managed MCP Server](https://img.shields.io/badge/Managed_MCP_Server-read--only-6933FF?logo=cockroachlabs&logoColor=white)](https://www.cockroachlabs.com/docs/stable/cockroachdb-and-ai) | The app itself is the MCP client, not just a developer's IDE — `GET /api/v1/incidents/open` and the UI's "Ask via MCP" (ADR 003) |
| **Agent Pattern** | [![Agent Pattern](https://img.shields.io/badge/5_agents-1_write_path-2563EB?logo=python&logoColor=white)](agents/orchestrator.py) | Orchestrator · Correlation · Remediation · Memory · Query. `memory_agent.py` is the *only* module permitted to write state |
| **Embeddings** | [![Titan](https://img.shields.io/badge/Amazon_Titan-Embed_Text_v2-FF9900?logo=amazonwebservices&logoColor=white)](https://aws.amazon.com/bedrock/) | Alert → 1024-dim vector, matching the `VECTOR(1024)` schema |
| **Reasoning** | [![Claude Sonnet 4.5](https://img.shields.io/badge/Claude_Sonnet_4.5-on_Bedrock-FF9900?logo=amazonwebservices&logoColor=white)](https://aws.amazon.com/bedrock/) | Next-step proposal over matched precedent, with deterministic precedent-replay fallback so the flow demos even when throttled |
| **Compute** | [![AWS Lambda](https://img.shields.io/badge/AWS_Lambda-python3.14-FF9900?logo=awslambda&logoColor=white)](https://aws.amazon.com/lambda/) | Stateless orchestrator, deliberately **no provisioned concurrency** — every invocation proves cold recovery (ADR 002, [`infra/template.yaml`](infra/template.yaml)) |
| **Backend** | [![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) [![psycopg](https://img.shields.io/badge/psycopg-3.3-336791?logo=postgresql&logoColor=white)](https://www.psycopg.org/psycopg3/) | Versioned gateway (`/api/v1`) around the orchestrator; psycopg 3 because psycopg2 has no 3.14 wheels |
| **Demo UI** | [![Gradio](https://img.shields.io/badge/Gradio-6.22-F97316?logo=gradio&logoColor=white)](https://gradio.app/) [![HF Spaces](https://img.shields.io/badge/🤗_Spaces-live-FFD21E)](https://huggingface.co/spaces/iarjunganesh/continuum) | Live incident console with recovery-timeline replay, the recalled precedent per step, and the committed failure evidence — reading straight from CockroachDB, in the viewer's own light or dark theme. Every card carries provenance badges naming the CockroachDB and AWS features that produced it (`⟲ resumed after kill`, `⌖ recalled #N of M`, the embedding and reasoning models, the runtime), and a legend names the **column each one is read from** — so the tool claims are checkable against the database, not taken on trust |
| **Observability** | [![structlog](https://img.shields.io/badge/structlog-JSON-4A90E2)](https://www.structlog.org/) | Structured event logging across every agent — no bare `print` |
| **Quality** | [![Ruff](https://img.shields.io/badge/Ruff-lint%20%2B%20format-D7FF64?logo=ruff&logoColor=111827)](https://docs.astral.sh/ruff/) [![Mypy](https://img.shields.io/badge/Mypy-type_checked-2A6DB2?logo=python&logoColor=white)](https://mypy-lang.org/) [![pytest](https://img.shields.io/badge/pytest-9.1-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/) | Lint → format → types → 85 unit + 9 integration tests → 100% coverage against a 90% gate → Codecov |

---

## Live Demo

| | |
| --- | --- |
| **App** | [https://huggingface.co/spaces/iarjunganesh/continuum](https://huggingface.co/spaces/iarjunganesh/continuum) *(deploys on push to `main`)* |
| **Orchestrator** | Live on AWS Lambda — `continuum-orchestrator`, eu-central-1 (stack `continuum`), deployed from CI on a version tag ([ADR 010](docs/adr/010-deploy-on-tag-from-ci.md)). No provisioned concurrency: **cold start 1806 ms init, 130 MB / 512 MB** (sampled 2026-08-08 on the current build). Warm environments *are* reused between back-to-back invocations, and it doesn't matter — the orchestrator re-reads CockroachDB first either way, so the guarantee never rests on the container being new. [`docs/DEPLOY.md`](docs/DEPLOY.md) is the authority on what is currently live |
| **Demo Video** | *Not yet recorded.* Recording script: [`submission/DEMO_SCRIPT.md`](submission/DEMO_SCRIPT.md) |
| **Try It Now** | `make chaos-demo` — kill the agent mid-incident, watch it resume from CockroachDB |

Submission checklist: [`submission/SUBMISSION.md`](submission/SUBMISSION.md) · Judging alignment + project story: [`submission/DEVPOST.md`](submission/DEVPOST.md) · Cost model: [`submission/COSTS.md`](submission/COSTS.md)

### Run it yourself — the interactive notebook

[![Open in Jupyter](https://img.shields.io/badge/Demo-Jupyter%20Notebook-F37626?logo=jupyter&logoColor=white)](notebooks/DEMO_RUNBOOK.ipynb)

**[`notebooks/DEMO_RUNBOOK.ipynb`](notebooks/DEMO_RUNBOOK.ipynb)** — a self-contained walkthrough of the kill-and-recover sequence. The recovery guarantee is easy to assert and hard to believe without watching it, so step through it yourself rather than taking the README's word.

| Section | Needs a local API? | What you'll see |
| --- | --- | --- |
| **1 — Fire a synthetic alert** | No | Recovery read runs *before* any reasoning; correlation finds a precedent |
| **2 — Read state back over MCP** | No | The app calling the Managed MCP Server's read-only SQL tool, live (ADR 003) |
| **3 — Advance one step** | No | Two `SERIALIZABLE` commits per step with the execution window between them |
| **4 — The kill** | **Yes** | A real `SIGKILL` landing mid-step — no graceful shutdown, no checkpoint call |
| **5 — State outlived the process** | **Yes** | The row sitting in `executing` with nothing alive to own it — *the whole thesis* |
| **6 — The recovery** | **Yes** | That exact step re-executed, not skipped and not duplicated |

```bash
pip install -r requirements.txt jupyter
make run-api                      # in a separate terminal
jupyter lab notebooks/DEMO_RUNBOOK.ipynb
```

Setup notes and conventions: [`notebooks/README.md`](notebooks/README.md).

---

## Captured Evidence

Judge-facing evidence — real runs with raw CockroachDB snapshots, structured logs, and provenance manifests recording the exact commit, cluster and models used. Index: [`assets/README.md`](assets/README.md).

**A real kill-and-recover run is captured and committed**: [`assets/chaos-run/local-4789422d/`](assets/chaos-run/local-4789422d/) — a live orchestrator hard-killed mid-step (real `SIGKILL`, pid 40760, no graceful shutdown), read back out of the database at three phases:

| Phase | What CockroachDB said |
| --- | --- |
| `01-before-kill` | step 0 `executing`, process alive |
| `02-frozen` | **process dead — the step still `executing`, with nothing alive to own it** |
| `03-after-resume` | incident `resolved`, all 3 steps `executed` exactly once, none duplicated |

Captured by `make chaos-capture`, which performs the kill *and* records it, and marks the folder `FAIL` rather than emitting evidence if the kill misses the execution window or a step runs twice. `correlation_source` and `reasoning_source` both read `bedrock`, so the live AWS path is provable from the rows rather than assumed.

Alongside it: [`assets/resilience-run/`](assets/resilience-run/) (kill storms, AWS-initiated Lambda timeouts, exactly-once under 50-way concurrency, vector search to 10,000 vectors), [`assets/deploy-restart-run/`](assets/deploy-restart-run/) (the function's code replaced under an open incident), and [`assets/provider-evidence/`](assets/provider-evidence/) — the same facts in Cockroach Labs' and Hugging Face's own consoles, screens this project cannot fake.

> **Still pending:** console screenshots for the chaos run, and an equivalent capture driven by cold Lambda invocations rather than a local process. Recovery on the deployed function is already evidenced **five** other ways: the deploy-restart drill, the AWS-timeout suite where AWS performs the kill, cold-invocation latencies in [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md), durable steps recording `runtime: lambda` alongside the model ids that produced them, and — since 2026-08-08 — the function's own CloudWatch logs, where `recovered_incident_state` shows `last_step_index` advancing across separate cold invocations of one `correlation_id` ([`assets/provider-evidence/16.lambda-recovery-reads.txt`](assets/provider-evidence/16.lambda-recovery-reads.txt)). Open gaps are tracked in [`submission/SUBMISSION.md`](submission/SUBMISSION.md).

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/iarjunganesh/continuum.git
cd continuum

# 2. Configure (CockroachDB Cloud free tier + AWS credentials)
cp .env.example .env    # fill in COCKROACH_DATABASE_URL + AWS keys

# 3. Install (requires Python 3.14)
make install

# 4. Apply schema + seed synthetic incident history (with embeddings)
make migrate
make seed-data

# 5. Run the API + demo UI
make run-api
make run-ui

# 6. The resilience demo — kills the agent mid-step, proves recovery
make chaos-demo
```

### On Windows — PowerShell 7+

Windows has no `make`, so every step has a direct equivalent. The `Makefile` stays the source of
truth for *what* each step does; this is the same work, typed differently.

```powershell
# 1. Clone
git clone https://github.com/iarjunganesh/continuum.git
cd continuum

# 2. Configure
Copy-Item .env.example .env    # fill in COCKROACH_DATABASE_URL + AWS keys

# 3. Install (requires Python 3.14)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. Apply schema + seed synthetic incident history
.\scripts\migrate_and_seed.ps1              # add -Offline for deterministic vectors, no AWS
                                            # -SkipSeed for schema only, -Count N to resize

# 5. Run the API + demo UI (separate terminals)
python -m uvicorn api.main:app --port 8000
python ui/app.py

# 6. The resilience demo — kills the agent mid-step, proves recovery
.\scripts\chaos_demo.ps1
```

Every other `make` target is a one-line recipe you can read straight out of the `Makefile` — most
are a single `python scripts/….py`. The ones used most often:

| `make` target | PowerShell |
| --- | --- |
| `make probe-bedrock` | `python scripts/probe_bedrock.py` |
| `make check-drift` | `python scripts/check_drift.py` |
| `make chaos-capture` | `python scripts/chaos_capture.py` (add `--pause` to hold for screenshots) |
| `make test` | `pytest tests/unit tests/integration -v` |
| `make lint` | `ruff check . ; ruff format --check .` |
| `make typecheck` | `mypy agents/ api/ observability/ config.py` |
| `make coverage` | `pytest tests/unit tests/integration --cov=agents --cov=api --cov=observability --cov-report=term-missing` |

Two targets are POSIX-only by design and have `.ps1` equivalents rather than translations —
`make chaos-demo` (backgrounding and `sleep`) and `make deploy` (`$$VAR` expansion). Use
`.\scripts\chaos_demo.ps1` and the steps in [`docs/DEPLOY.md`](docs/DEPLOY.md).

The API is versioned under `/api/v1` — e.g. `GET /api/v1/health`, `POST /api/v1/alert` — so the wire contract can evolve without breaking the Gradio UI or demo scripts.

---

## Synthetic Demo Data

40 resolved historical incidents across 5 fictional services (`checkout-api`, `auth-service`, `recommendation-engine`, `search-index`, `billing-worker`), each seeded with its **actual remediation path** (e.g. `drain_connection_pool → restart_connection_pool → verify_connections_healthy`) — so when a live alert correlates with a precedent, the Remediation Agent has real steps to replay, not just a summary. Regenerate anytime:

```bash
python scripts/generate_synthetic_incidents.py --out data/synthetic/incidents_seed.jsonl --count 40
```

**Seeding without Bedrock.** Real Titan vectors for the 40 seed incidents are **committed** at [`data/synthetic/seed_embeddings.json`](data/synthetic/seed_embeddings.json), so honest semantic correlation needs no AWS call at seed time:

```powershell
python scripts/seed_memory.py --file data/synthetic/incidents_seed.jsonl `
    --from-fixture data/synthetic/seed_embeddings.json --replace-embeddings
```

`--replace-embeddings` overwrites vectors that already exist; without it the insert is `ON CONFLICT DO NOTHING`, which is right for topping up incidents and silently wrong when the point of the run is to replace the vectors. `make seed-data` embeds via a live Titan call per record instead; `make seed-data-offline` uses deterministic vectors that populate the table with **no AWS dependency at all** but are explicitly not semantically meaningful — measured precision@1 **55% vs 98%** for Titan on the same corpus, so prefer the fixture for anything a reader will interpret as correlation.

---

## Project Structure

```text
continuum/
├── agents/
│   ├── orchestrator.py        # Lambda entrypoint — recovery read FIRST, one step per invocation
│   ├── correlation_agent.py   # Bedrock Titan embeddings + CockroachDB vector search
│   ├── memory_agent.py        # THE single write path to incidents/remediation_steps
│   ├── remediation_agent.py   # Claude-on-Bedrock reasoning + precedent-replay fallback
│   └── query_agent.py         # CockroachDB Managed MCP Server client (read-only live queries)
├── api/main.py                # FastAPI gateway, versioned under /api/v1
├── ui/app.py                  # Gradio — incident console, timeline replay, failure evidence
├── config.py                  # pydantic-settings; tolerates unknown env vars by design
├── observability/structured_logger.py   # structlog JSON — no bare print anywhere
├── prompts/
│   ├── remediation_agent.txt  # Claude reasoning prompt — data, not code (loaded at import)
│   └── README.md              # why prompts are data and why loading is import-time
├── infra/
│   ├── schema.sql             # incidents · remediation_steps · incident_embeddings VECTOR(1024)
│   ├── lambda_handler.py      # Lambda package entrypoint
│   ├── template.yaml          # AWS SAM — deliberately NO provisioned concurrency (ADR 002)
│   └── requirements-lambda.txt   # what ships INTO the function (not the root requirements.txt)
├── scripts/
│   │                          # — data —
│   ├── generate_synthetic_incidents.py   # corpus incl. historical remediation paths
│   ├── seed_memory.py         # loads incidents + step history + embeddings
│   ├── capture_seed_embeddings.py        # capture real Titan vectors once, seed --from-fixture
│   ├── synthetic_vectors.py   # deterministic vectors for a zero-AWS seed
│   ├── export_memory.py       # snapshot the memory layer to data/snapshots/*.jsonl
│   ├── restore_memory.py      # put a snapshot back — idempotent, retries on contention
│   ├── migrate_and_seed.ps1   # Windows path for migrate + seed, no make required
│   ├── local_cluster.py       # single-node CockroachDB in Docker — where benchmarks belong
│   │                          # — the demo beat —
│   ├── chaos_kill.py          # cross-platform hard kill (psutil)
│   ├── chaos_capture.py       # the same kill, recorded → assets/chaos-run/ evidence
│   ├── chaos_demo.ps1         # Windows kill-and-recover sequence
│   ├── demo_run.py            # drives one remediation step per --tick
│   ├── generate_demo_voiceover.py        # Polly narration + caption track (owns the words)
│   │                          # — evidence —
│   ├── benchmark.py           # latency → docs/BENCHMARKS.md
│   ├── resilience_bench.py    # correctness under adversity → docs/RESILIENCE.md
│   ├── deploy_restart_drill.py           # redeploy under an open incident, prove the resume
│   ├── evidence.py            # run-scoped evidence folders + provenance manifest
│   ├── build_charts.py        # theme-aware charts from the newest evidence run
│   ├── build_obs_assets.py    # 1080p OBS sources from provider-evidence (pans, never downscales)
│   ├── redact_evidence.py     # mask a face or an account id in evidence PNGs — declared, idempotent
│   │                          # — release gates —
│   ├── check_drift.py         # docs vs repo: versions, counts, links, generated files
│   ├── build_devpost_readme.py           # regenerates the Devpost paste mirror from README.md
│   ├── preflight_deploy.py    # six deploy preconditions, all reported at once
│   └── probe_bedrock.py       # is live Bedrock open today? quotas are dynamic (ADR 008)
├── tests/
│   ├── unit/                  # recovery-semantics tests (all I/O mocked at the import boundary)
│   ├── integration/           # vs a real cluster — recovery, real SIGKILL, vector plan, snapshot
│   └── load/k6_smoke.js       # read-path smoke load (health + MCP-backed /incidents/open)
├── data/
│   ├── synthetic/             # generated incident corpus + alert stream (synthetic, always)
│   └── snapshots/             # memory exports — insurance against the cluster lapsing
├── docs/
│   ├── ARCHITECTURE.md · DEPLOY.md · BENCHMARKS.md · RESILIENCE.md · CLUSTER_OPS.md
│   └── adr/                   # 10 Architecture Decision Records
├── submission/                # judge-facing packet
│   └── SUBMISSION.md · DEVPOST.md · DEVPOST_README.md · DEMO_SCRIPT.md · COSTS.md
├── assets/                    # judge-facing evidence — see assets/README.md
│   ├── architecture/          # mermaid source + brand-themed SVG/PNG renders
│   ├── charts/                # generated benchmark charts (make charts) — never screenshots
│   ├── chaos-run/             # captured kill-and-recover runs (evidence/ + screenshots/)
│   ├── provider-evidence/     # the same facts in Cockroach Labs' and Hugging Face's own consoles
│   ├── resilience-run/        # kill storms, Lambda timeouts, exactly-once, vector scale
│   ├── deploy-restart-run/    # the code swapped under an open incident, and the resume
│   ├── demo-cards/            # banner + sign-off cards (SVG source, 16:9 video PNGs)
│   ├── demo-voiceover/        # generated Polly narration, one clip per beat
│   ├── demo-video/            # final cut, captions, per-beat takes
│   └── logo.svg
├── notebooks/DEMO_RUNBOOK.ipynb   # run the recovery demo against a live cluster, no local setup
├── Makefile                   # source of truth for how to run anything
├── samconfig.toml             # checked in, minus the cluster credential — reproducible deploys
├── pyproject.toml             # version, ruff + mypy config, coverage gate
├── requirements.txt           # floor-pinned with major-version caps
├── .env.example               # every setting, placeholder values only
├── .mcp.json                  # MCP server config — environment expansion, no secrets
├── .github/workflows/         # ci.yml · deploy.yml · release.yml · sync-to-hf-space.yml
└── CHANGELOG.md · CLAUDE.md · CONTRIBUTING.md · SECURITY.md · LICENSE
```

---

## Production & Quality

```text
push → ruff lint → ruff format --check → mypy → Devpost mirror freshness
     → ephemeral single-node CockroachDB → schema apply
     → pytest (85 unit + 9 integration) → coverage (≥90% gate, 100% measured) → Codecov
push to main → auto-sync to Hugging Face Space (public demo)
tag v*.*.*   → GitHub Release, notes pulled from CHANGELOG.md
             → deploy the orchestrator to AWS Lambda (OIDC, no stored keys)
                 → assert CodeSha256 actually moved → smoke-test the deployed package
```

**A tag deploys the function** ([ADR 010](docs/adr/010-deploy-on-tag-from-ci.md)), so the deployed orchestrator and the newest tag cannot drift. Deliberately not on every push to `main` — that would redeploy the live function during ordinary work, including while the demo is being recorded against it.

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml), [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml), [`.github/workflows/release.yml`](.github/workflows/release.yml), and [`docs/DEPLOY.md`](docs/DEPLOY.md).

The unit suite (85 tests, one file per agent/module, 100% measured coverage against a 90% CI gate) pins the properties the demo depends on: recovery read happens before any write, each step commits inside an explicit `SERIALIZABLE` transaction, interrupted steps are re-executed (never skipped, never duplicated), a forward step is claimed exactly once under concurrent invocations, and incidents resolve atomically with the final step.

[`tests/integration/test_recovery_e2e.py`](tests/integration/test_recovery_e2e.py) drives that same resume-and-exactly-once contract against the real schema on a real CockroachDB instance CI spins up — not just against mocks — and [`tests/integration/test_chaos_kill_e2e.py`](tests/integration/test_chaos_kill_e2e.py) goes one step further: it spawns the orchestrator as a real subprocess and hard-kills it mid-step with [`scripts/chaos_kill.py`](scripts/chaos_kill.py) (a real `SIGKILL`/`TerminateProcess`, no graceful shutdown), then asserts a cold restart resumes the interrupted step exactly once from CockroachDB. The same script drives the literal process-kill beat live in the demo.

Beyond tests: structlog JSON logging across every agent, secrets via environment only, least-privilege IAM, and documented scope cuts (ADR 006) rather than hidden ones. Security posture and known limitations: [`SECURITY.md`](SECURITY.md). Cost model and guardrails: [`submission/COSTS.md`](submission/COSTS.md).

### Load & Resilience

What a remediation step actually costs, end to end: the CockroachDB legs (recovery read, both transaction commits, C-SPANN vector search, the full cold-resume path), the Bedrock legs (real Titan embedding), and the same work measured **on the deployed Lambda** rather than predicted from a workstation. Every run records which path actually executed — `correlation_source` / `reasoning_source` are counted, not assumed, so a throttled account can't quietly publish cheaper numbers under a Bedrock headline. `make benchmark` (add `--with-bedrock --lambda-n N` for the AWS legs; the default run needs no AWS). Full tables, methodology and caveats: [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md). Benchmarks run against `make local-cluster`, not the Cloud cluster serving the demo — [`docs/CLUSTER_OPS.md`](docs/CLUSTER_OPS.md) says which commands belong where, and why.

Speed is the less interesting half. The claim this project exists to make is about **correctness when things go badly**, so that is measured too — every number below counted from durable CockroachDB rows rather than from a log, against the live cluster and the deployed function. `make resilience-bench`; full method, sample sizes and caveats in [`docs/RESILIENCE.md`](docs/RESILIENCE.md), raw evidence under [`assets/resilience-run/`](assets/resilience-run/).

| Failure mode | Result |
| --- | --- |
| Kill storm — 50 incidents interrupted mid-step | **50 resumed · 0 duplicated · 0 lost** |
| Real `SIGKILL` against a live process | 10 kills · **10 resumed · 0 duplicated** |
| **AWS Lambda timeout — AWS does the killing** | 15 invocations · **15 killed by AWS · 15 resumed exactly once** |
| **Deploy mid-incident — the code replaced underneath an open step** | `sam deploy` swapped the artifact · **resumed on the new build, exactly once** |
| Exactly-once under concurrent claimants | 100 trials, 5 levels up to 50-way · **0 violations** |
| Concurrent agents | 10 / 50 / 100 · 53.7 completed/s · **0 failures** |
| C-SPANN vector search, 100 → 10,000 vectors | 43 → 77 ms vs full scan 40 → 582 ms — **7.5× faster** |

The Lambda-timeout row is the one that can't be argued with: the process isn't killed by our own script but by **AWS terminating the function**, with no signal the runtime can catch and no opportunity to checkpoint. Every one of those recovered exactly once.

The deploy row is the only one that doesn't kill anything. It replaces the *code* under an incident already frozen in `executing` — a real `sam build` + `sam deploy` — and the cold invocation afterwards resumes that step on a build that did not exist when the step began. That's the failure an on-call engineer actually causes, by shipping a fix while an incident is open, and the durable row is the only thing bridging the two versions. `make deploy-restart-drill`; it compares `CodeSha256` before and after and **fails if the code didn't actually change**, because a no-op deploy would otherwise pass while proving nothing. Evidence: [`assets/deploy-restart-run/`](assets/deploy-restart-run/).

[`tests/load/k6_smoke.js`](tests/load/k6_smoke.js) ramps concurrent users against `/api/v1/health` and the MCP-backed `/api/v1/incidents/open`, so the measurement covers the live MCP round trip rather than just FastAPI. It deliberately does **not** hammer `POST /alert`: that drives real state through the single write path, and exercising the forward-step claim outside controlled conditions would fabricate incidents rather than test them — exactly-once is proven in the integration suite instead.

```bash
winget install k6   # or: brew install k6
make load-test                                        # local API
k6 run -e BASE_URL=https://<host> tests/load/k6_smoke.js   # deployed
```

---

## Roadmap (Post-Hackathon)

- Real alert-source integrations (PagerDuty/Opsgenie webhook ingestion) in place of the synthetic stream
- Multi-region incident correlation via `REGIONAL BY ROW` incident tables
- Contradiction/drift detection across recurring incident patterns
- Slack/Teams remediation-approval loop before a proposed step executes

---

## Disclosure & Disclaimer

Built solo during the Submission Period (June 30 – August 18, 2026) with **Claude Code** as an AI coding assistant, per the hackathon's disclosure requirement. No pre-existing code was incorporated. All incident, alert, and remediation data is synthetic; Continuum is a technology demonstration, not a production incident-management tool, and is not affiliated with any company's real infrastructure.

> *Built by [Arjun Ganesh](https://github.com/iarjunganesh) for the [CockroachDB × AWS Hackathon 2026](https://cockroachdb-ai.devpost.com/).*

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/demo-cards/signoff-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/demo-cards/signoff-light.svg">
    <img width="560" src="assets/demo-cards/signoff-light.svg"
         alt="The memory outlived the failure. — Continuum"/>
  </picture>
</p>
