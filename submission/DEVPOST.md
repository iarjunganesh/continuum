# Devpost Submission — Continuum

## The Hackathon

**[CockroachDB × AWS Hackathon — Build with Agentic Memory](https://cockroachdb-ai.devpost.com/)**

> *Agents that think. Agents that act. Agents that remember; reliably, globally, at any scale.*

Hosted by **Cockroach Labs**, organized by Devpost.

Build agentic applications that leverage CockroachDB's distributed AI capabilities on AWS. AI agents
require persistent memory that never fails; CockroachDB serves as the globally distributed,
always-on system for agentic memory — handling conversation history, embeddings, and transactional
data at scale.

### Timeline (all times Eastern)

| Phase | Window |
| --- | --- |
| **Submission Period** | June 30, 2026 (10:00 am) – **August 18, 2026 (5:00 pm)** |
| **Judging Period** | August 19, 2026 (10:00 am) – September 15, 2026 (5:00 pm) |
| **Winners Announced** | On or around September 21, 2026 (3:00 pm) |

### Prizes — $8,750 total

| Place | Award |
| --- | --- |
| **1st** | $5,000 USD · blog feature · swag |
| **2nd** | $2,500 USD · swag |
| **3rd** | $1,250 USD · swag |

### Required project requirements

Build an agentic application using CockroachDB as persistent memory on AWS, using **at least two**
CockroachDB tools and **at least one** AWS service.

| CockroachDB tools (≥ 2 required) | Continuum |
| --- | --- |
| Cloud Managed MCP Server | ✅ `agents/query_agent.py` — read-only, called by the app at runtime |
| Distributed Vector Indexing | ✅ `incident_embeddings` C-SPANN index, live correlation queries — **7.5× faster than a full scan at 10,000 vectors** against CockroachDB Cloud, and 98% precision@1 on failure-mode retrieval, with the query plan pinned by an integration test and the precision figure recomputed by `make precision-check` |
| ccloud CLI (Agent-Ready) | ❌ evaluated and deliberately cut — see ADR 004 |
| Agent Skills Repo (Open Source) | ❌ not used |

| AWS services (≥ 1 required) | Continuum |
| --- | --- |
| Bedrock | ✅ Titan Text Embeddings V2 + Claude Sonnet 4.5 |
| Lambda | ✅ orchestrator execution, no provisioned concurrency |
| SAM · IAM | ✅ infrastructure as code; Bedrock-invoke-only credentials |
| Polly | ✅ demo narration + caption timings (`scripts/generate_demo_voiceover.py`) — production tooling, not the running app |
| ECS/EKS · S3 · SageMaker · others | ❌ not used |

### Required submission materials

- Public open-source repository with README, dependencies, configurations, and setup instructions,
  with a **detectable open-source license**
- Functional demo app URL
- Video demonstrating the submission **and the memory layer** — under 3 minutes, YouTube/Vimeo
- Documentation identifying which CockroachDB and AWS tools were used
- *Optional:* architecture diagram, and feedback on CockroachDB AI tools

### Eligibility rules that shaped this build

- **"Projects must be newly created by the Entrant during the Submission Period."** No pre-existing
  code was incorporated into Continuum.
- AI coding assistants are explicitly permitted; any pre-existing code must be disclosed. Continuum
  was built with **Claude Code** — disclosed in the README.

Tracking checklist: [`SUBMISSION.md`](SUBMISSION.md)

---

## Devpost Form Answers

Every field on the Devpost submission form, with the exact text to paste. Fields marked
**public** appear on the project gallery page; the rest go to judges and organizers only.
Nothing here is a placeholder — an unanswerable field says so explicitly.

### General info

- [x] **Project name** *(public)*

  > `Continuum`

- [x] **Elevator pitch** — short tagline *(public)*

  > Kill the agent mid-incident. It resumes the exact step it died on — because its memory lives in CockroachDB, not the process.

- [x] **Built with** — up to 25 tags *(public)*

  > `python` · `fastapi` · `uvicorn` · `pydantic` · `psycopg3` · `cockroachdb` · `cockroachdb-cloud` ·
  > `distributed-vector-indexing` · `model-context-protocol` · `amazon-bedrock` · `amazon-titan` ·
  > `claude` · `aws-lambda` · `aws-sam` · `aws-iam` · `amazon-polly` · `gradio` · `huggingface-spaces` ·
  > `structlog` · `pytest` · `ruff` · `mypy` · `github-actions` · `docker` · `k6`

  Exactly 25. Every one is a dependency, a service the app calls, or a gate in CI — nothing
  aspirational.

- [x] **Video demo link** — https://youtu.be/LwD8__sKqa0 (uploaded 2026-08-12, 2:55.7, under the 3-minute cap).
      Shows the memory layer rather than only the app: beats 6–8 are one continuous take in which a
      live orchestrator is hard-killed mid-step and a cold Lambda invocation resumes that exact
      `step_index` out of CockroachDB. **Visibility confirmed Public** on 2026-08-13, which is a rules
      requirement: an unauthenticated fetch of the watch page reports `"isUnlisted":false` and
      `"isPrivate":false` in its own player metadata. Worth recording *how*, because a plain 200 does
      not distinguish Public from Unlisted — both serve the page to a signed-out visitor.

### Additional info (judges and organizers)

- [x] **URL to your functional demo application**

  > `https://huggingface.co/spaces/iarjunganesh/continuum`

- [x] **Testing credentials or instructions**

  > No credentials, login, or setup required — the Space is public and read-only.
  >
  > One thing to know before you click: **the panels are intentionally blank on first paint. Press
  > "Refresh" to load live state from CockroachDB.** Auto-refresh is disabled on purpose — a
  > Request-Unit audit measured the polling timer at roughly 50 RU per refresh per open browser tab,
  > which over a four-week judging period would consume a large share of the cluster's monthly
  > allowance while nobody was watching. Manual refresh is the trade I chose.
  >
  > What you'll see: seeded synthetic incidents with their remediation timelines, each step carrying
  > provenance badges read directly from durable columns — the embedding and reasoning model ids, the
  > vector-search recall rank and L2 distance, the runtime (`λ` when the step ran on Lambda), and
  > `⟲ resumed after kill` where a cold invocation picked up an interrupted step. Every badge is a
  > column value, never inferred, so anything the console asserts can be checked by querying the
  > database. The "Ask via MCP" button runs a live query through the CockroachDB Cloud Managed MCP
  > Server at request time.
  >
  > The Space cannot start a new incident — that is deliberate, not missing. Every write to incident
  > state goes through a single module (ADR 001), and adding a UI write path would weaken the exact
  > property the project exists to prove. To drive the loop yourself, clone the repo and follow the
  > Quick Start; `make chaos-demo` (or `scripts/chaos_demo.ps1` on Windows) performs the kill and the
  > recovery end to end against your own cluster.

- [x] **URL to your open source and public code repository**

  > `https://github.com/iarjunganesh/continuum`

- [x] **URL to your open-source license file**

  > `https://github.com/iarjunganesh/continuum/blob/main/LICENSE`

  MIT, detected by GitHub and shown in the repository's **About** sidebar.

- [x] **Which CockroachDB tools are used?** *(public)*

  > ☑ **Distributed Vector Indexing**
  > ☑ **CockroachDB Cloud Managed MCP Server**
  >
  > Not claimed: ccloud CLI and the Agent Skills Repo. Both were evaluated and deliberately cut
  > (ADR 004) rather than added thinly to inflate a tool count.

- [x] **Which AWS Services are used?** *(public)*

  > ☑ **AWS Lambda** ☑ **Amazon Bedrock**
  >
  > Also used, if the form allows them: **AWS SAM**, **AWS IAM**, **Amazon Polly** (demo narration —
  > production tooling, not the running app).

- [x] **How did you meaningfully integrate the above components?**

  > Each of the four is load-bearing: remove any one and the demo's central claim stops being
  > provable.
  >
  > **CockroachDB — Distributed Vector Indexing.** `incident_embeddings.embedding` is a
  > `VECTOR(1024)` column with a C-SPANN index prefixed by `service`. The Correlation Agent's live
  > query filters on structured columns *and* ranks by `<->` L2 distance in a single round trip, so
  > precedent lookup is ordinary SQL against the same store that holds the transactional state — no
  > second datastore, no consistency gap. Two things make this a real integration rather than a
  > claim. First, an integration test asserts the **query plan**, because for a long time it was
  > wrong: joining `incidents` in the same statement as the `<->` ordering made the planner fall back
  > to `spans: FULL SCAN`. Results stayed correct, so nothing failed and nothing looked wrong while
  > the headline integration sat idle. A CTE restored it, and a second test fails deliberately if a
  > future CockroachDB version makes that workaround unnecessary. Second, I measured whether the
  > retrieval *meant* anything: the seeded vectors were originally deterministic hashes my own
  > generator documents as "not semantically meaningful", scoring **precision@1 of 55%**. Real Titan
  > vectors took it to **98%** — 39 of 40 nearest neighbours sharing the failure mode. That figure is
  > not a number I once measured and then quoted: `make precision-check` recomputes both arms from the
  > committed fixture with no AWS call and no cluster, and three unit tests fail if the Titan arm ever
  > drops below 90% or the meaningless baseline ever catches up. At 10,000 vectors the index is
  > **7.5× faster than the equivalent full scan** against CockroachDB Cloud — a single-node local
  > cluster narrows that gap, because the full scan it has to beat is far cheaper there.
  >
  > **CockroachDB — Cloud Managed MCP Server.** `agents/query_agent.py` is the *application's own*
  > MCP client — the official `mcp` SDK over streamable HTTP, in read-only mode — not a developer
  > convenience wired into an IDE. It backs `GET /api/v1/incidents/open` and the Gradio console's
  > "Ask via MCP" button, so a question like "which incidents are open and what step are they on"
  > travels through the protocol at request time, in production, on behalf of an end user (ADR 003).
  >
  > **AWS Lambda.** The orchestrator's deployed home, on the `python3.14` runtime, with
  > **provisioned concurrency deliberately absent** — its absence is a reviewable line in
  > `infra/template.yaml`, not a console setting (ADR 002). That is the integration's whole point:
  > nothing keeps the function warm, and the orchestrator re-reads CockroachDB *first* on every
  > invocation regardless of whether the execution environment is brand new or reused — so the
  > guarantee never rests on the container being cold. Four successive `sam remote invoke` calls
  > drove one incident 0 → 1 → 2 → `resolved`, each resuming from the database with the same
  > `incident_id`. Since `v0.9.5` the function deploys from
  > CI on a version tag via GitHub OIDC with no stored AWS keys, asserting the code hash actually
  > moved and smoke-testing the deployed package, so the running function and the newest release
  > cannot silently diverge (ADR 010).
  >
  > **Amazon Bedrock.** Titan Text Embeddings V2 turns each alert into the 1024-dim vector the schema
  > stores; Claude Sonnet 4.5 reasons over the matched precedent to propose the next remediation step.
  > Both paths degrade rather than fail — a red Bedrock endpoint means "no precedent" or a
  > deterministic precedent replay, never an aborted incident — and because silent degradation would
  > let a throttled account produce a demo that looks fine while never calling Bedrock, **every step
  > persists `correlation_source` / `reasoning_source` and the model ids it actually used**. A step
  > that fell back names no model at all. So "Bedrock ran" is a column you can query, not a sentence
  > in my README.
  >
  > **How they compose.** The differentiating property is the join of the two databases-in-one:
  > `SERIALIZABLE` incident state and the vector index live in the same CockroachDB store, so a step
  > commits as `executing` *before* its execution window and `executed` after, in two explicit
  > transactions, with the forward-step claim as `INSERT … ON CONFLICT DO NOTHING`. Hard-kill the
  > process mid-step and the next cold Lambda invocation finds the frozen `executing` row and re-runs
  > that exact step — exactly once, even under concurrent invocations. Measured, not asserted: 50
  > interrupted incidents → 50 clean resumes, 0 duplicated actions; 15 invocations killed by **AWS
  > itself** via Lambda timeout, where no signal is delivered and nothing gets a chance to checkpoint,
  > all recovering exactly once; 0 exactly-once violations across 100 trials up to 50-way
  > concurrency; and a real `sam deploy` swapping the function's code underneath an open incident,
  > after which the cold invocation resumed that step on the **new build**, with the durable
  > CockroachDB row as the only thing bridging the two versions. Method and raw evidence:
  > [`docs/RESILIENCE.md`](../docs/RESILIENCE.md).

- [x] **What date did you start this project? (MM-DD-YY)**

  > `07-04-26`

  First commit `0be07bb`, 2026-07-04 — inside the Submission Period, which opened 2026-06-30.
  The public history is verifiable: `git log --reverse` on the repository above.

- [x] **Please explain any pre-existing code or work incorporated into the Project.**

  > **None.** Continuum was created from an empty repository on 2026-07-04, inside the Submission
  > Period, and every line was written during it. No code was ported in from any prior project of
  > mine or anyone else's, and no starter template or scaffold was used.
  >
  > What *was* carried over, since the rules ask for disclosure rather than purity: general
  > architectural patterns and personal conventions — a single-write-path memory module, ADRs as
  > numbered files, structlog JSON logging, Ruff/mypy/coverage gates in CI. Patterns, not source.
  > This is written into the project's own standing constraints (`CLAUDE.md`) so it holds for every
  > future change rather than being asserted once at submission time.
  >
  > Third-party dependencies are the standard permitted kind and are all declared in
  > `requirements.txt` with floor pins and major-version caps: FastAPI, psycopg 3, boto3, the
  > official `mcp` SDK, Gradio, Pydantic, structlog, pytest, Ruff, mypy.
  >
  > All incident, alert, and remediation data is **synthetic** and generated by scripts in this
  > repository (ADR 005). No real company names, no real infrastructure, no customer data, no PII.

- [x] **Which AI tools have you leveraged while working on this project?**

  > **Claude Code** (Anthropic) was the only AI coding assistant used, throughout the build — for
  > implementation, refactoring, test authoring, documentation, and review. It is disclosed in the
  > README's "Disclosure & Disclaimer" section as well as here. Every design decision, and every
  > decision to *reject* something, is mine and recorded in the ADRs in `docs/adr/`; the ten ADRs are
  > the audit trail for that.
  >
  > Distinct from the above, and worth separating: **Claude Sonnet 4.5 and Amazon Titan Text
  > Embeddings V2 run inside the product itself** via Amazon Bedrock — they are runtime components
  > of the agent, not authoring tools.

- [x] **Describe your contribution** *(public)*

  > **Solo build — architecture, code, tests, infrastructure, evidence and documentation are all
  > mine.** 70+ commits, one author, public history from an empty repository on 2026-07-04 through
  > the `v1.0.0` submission release, entirely inside the Submission Period.
  >
  > **What I built:**
  >
  > - **The recovery mechanic itself** — the two-phase `SERIALIZABLE` step checkpoint that commits
  >   `executing` *before* the execution window and `executed` after, with the forward-step claim as
  >   `INSERT … ON CONFLICT DO NOTHING`. This is the whole project: it is what makes a hard kill land
  >   on durable state, and what makes the resume exactly-once under concurrent invocations.
  > - **Five agents behind one write path** — orchestrator (recovery-read-first control flow),
  >   correlation, remediation, memory, query. Only `memory_agent.py` may write incident state, so a
  >   resuming invocation can trust everything it reads.
  > - **Both CockroachDB integrations** — the `VECTOR(1024)` C-SPANN schema and the correlation query
  >   that filters and ANN-ranks in one round trip, and the application's own MCP client against the
  >   Cloud Managed MCP Server.
  > - **The AWS side** — SAM template, Bedrock Titan and Claude call paths with silent-degradation
  >   handling and durable provenance columns, least-privilege IAM, and deploy-on-tag from CI over
  >   GitHub OIDC with no stored keys.
  > - **The apparatus that tries to disprove the claim** — chaos-kill and capture harnesses, the
  >   resilience bench (kill storms, AWS-initiated Lambda timeouts, 50-way concurrency, vector search
  >   to 10,000 vectors), the deploy-restart drill, the clean-clone check, and a docs-drift checker.
  >   **That tooling is ~7,500 lines against ~2,100 lines of application code** — deliberately, because
  >   a resilience claim nobody tried to break is a slogan.
  > - **The judgment calls, and the retractions** — 10 ADRs, including the decision to *cut* a third
  >   CockroachDB tool rather than add it thinly. Several sections of this submission exist because I
  >   found my own claims wrong and said so: the vector index that was provably used over vectors that
  >   meant nothing (precision@1 55% → 98%), the query plan that had silently fallen back to a full
  >   scan, and a cluster outage I misdiagnosed from an error message instead of the billing page.
  >
  > **On AI assistance, since the rules ask.** I used **Claude Code** (Anthropic) throughout, for
  > implementation, refactoring, test authoring and documentation. It wrote code at my direction; it
  > did not decide what to build, what to measure, or what to throw away. Every architectural
  > decision — and every decision to reject something — is mine and is recorded in `docs/adr/` with
  > its reasoning, which is the audit trail for that claim. No pre-existing code, starter template or
  > scaffold was used, from any prior project of mine or anyone else's.

---

## Judging Alignment

The five criteria are **equally weighted**. Official descriptions quoted, followed by how Continuum
answers each.

| Criterion | Official description | How Continuum addresses it |
| --- | --- | --- |
| **Agentic Memory Design** | *"Whether CockroachDB meaningfully functions as production-grade memory layer"* | Dual memory in **one** CockroachDB store — ACID incident/remediation state *and* vector embeddings — not a toy chat log. Each step's checkpoint is an explicit `SERIALIZABLE` transaction, so a resuming invocation never reads a half-written state transition, and a forward step is claimed exactly once (`ON CONFLICT DO NOTHING`) even under concurrent invocations. |
| **Technical Implementation** | *"Quality software engineering and correct tool usage"* | Distributed Vector Indexing doing real correlation work; MCP Server as a live read-only query surface the app itself calls; a single-write-path Memory Agent enforced by convention and tests; recovery semantics pinned by CI — 88 unit tests (100% measured coverage against a 90% gate), plus integration tests driving the resume-and-exactly-once contract against a live CockroachDB instance rather than mocks. One (`test_chaos_kill_e2e.py`) hard-kills a real orchestrator subprocess mid-step with a genuine `SIGKILL` and asserts exactly-once cold recovery — the same script that drives the kill beat in the demo. |
| **Real-World Impact** | *"Meaningful use case and potential user value"* | Every engineering org runs production incidents, and the failure mode Continuum addresses is one on-call engineers actually hit: the conditions that cause an incident — resource exhaustion, node loss, deploy rollbacks, autoscaling churn — are the same conditions that kill the agent responding to it. Two parts of the value claim are measured rather than asserted. **The precedent is useful**: 98% precision@1 on failure-mode retrieval, recomputed from committed data by `make precision-check`, against 55% for vectors I can prove are meaningless. **The recovery is real**: 50 interrupted incidents resumed exactly once with 0 duplicated actions, including 15 killed by AWS itself, and one resumed across a live `sam deploy` that replaced the code mid-incident. What I deliberately do **not** claim is an MTTR number. Every incident here is synthetic (ADR 005), so there is no baseline to reduce, and quoting a percentage off a corpus I generated would be exactly the error the 55% → 98% retraction below is about. The honest statement is that the mechanism this depends on — retrieve a real precedent, survive the process dying — is demonstrated; what it saves a specific team is theirs to measure. |
| **Production Readiness** | *"Security, observability, scalability, and resilience"* | The kill-and-resume beat *is* the resilience proof, not a slide about it — and it's measured, not asserted: **50 interrupted incidents, 50 clean resumes, 0 duplicated actions, 0 lost steps**, plus **15 invocations killed by AWS itself** via Lambda timeout (no catchable signal, no chance to checkpoint) all recovering exactly once, **0 exactly-once violations across 100 trials up to 50-way concurrency**, and — the failure an on-call engineer actually causes — a **real `sam deploy` replacing the function's code underneath an open incident**, after which the cold invocation resumed that step on the new build, exactly once. Full method and raw evidence: [`docs/RESILIENCE.md`](../docs/RESILIENCE.md), `assets/resilience-run/`. structlog JSON logging throughout — including *on Lambda*, where it silently was not: `basicConfig()` is a no-op when the runtime has already installed a root handler, so every log line the deployed function emitted was discarded until 2026-08-07, and CloudWatch held only AWS's own START/END/REPORT lines. Secrets via environment only; least-privilege IAM; **the orchestrator deploys from CI on a tag via GitHub OIDC with no stored AWS keys** (ADR 010), asserting the code hash actually moved and smoke-testing the deployed package, so the running function and the newest release cannot drift; lint, format, type, and coverage gates in CI; explicit scope cuts documented in ADR 006 rather than hidden. |
| **Creativity & Originality** | *"Novel ideas or applications demonstrating agentic system insights"* | A literal, load-bearing answer to the hackathon's own framing — an agent whose memory goes offline doesn't degrade gracefully, it stops — built as the single demo beat rather than a footnote. |

---

## Elevator Pitch

**Devpost's tagline field is short — paste this one:**

> **Kill the agent mid-incident. It resumes the exact step it died on.**

Longer version, for the description field and anywhere with room:

> An autonomous incident-response agent that resumes the exact step it was killed on: kill the process mid-remediation, and the next cold invocation picks up the interrupted step from CockroachDB — not from scratch, and never a duplicate. Its memory lives in the database, not the process.

---

## Project Story

### Inspiration

Most agentic-memory demos store chat history and call it a day. But the conditions that cause real production incidents — resource exhaustion, node failure, deploy rollbacks, autoscaling churn — are exactly the conditions that kill the agent responding to them. The hackathon brief said it directly: *"an agent whose memory goes offline doesn't degrade gracefully, it stops."* Continuum is built as a direct, literal test of that failure mode, not a workaround for it.

### What it does

A synthetic alert fires. The Orchestrator (designed for AWS Lambda, deliberately never kept warm) reads CockroachDB **first, before any new reasoning** — recovering any open incident matching this alert. The Correlation Agent embeds the alert via Amazon Bedrock (Titan v2) and searches CockroachDB's native vector index for similar past incidents. The Remediation Agent proposes the next action, reasoning over the matched precedent via Claude on Bedrock (best-effort — a red Bedrock endpoint degrades correlation to "no precedent" rather than aborting the incident). Each step commits in two explicit `SERIALIZABLE` transactions — the proposed action and `executing` status together, then `executed` — with the `time.sleep` execution window between them. Kill the process mid-step (`chaos_kill.py`, no graceful shutdown), and the next cold invocation finds the step frozen in `executing` and **re-runs that exact step** — no restart from scratch, no duplicated work, no lost context.

### How we built it

Five agents, one write path: `orchestrator.py` (recovery-read-first control flow), `correlation_agent.py` (Bedrock embeddings + CockroachDB vector search), `remediation_agent.py` (Claude-on-Bedrock reasoning with a deterministic precedent-replay fallback), `memory_agent.py` — the *only* module permitted to write `incidents` or `remediation_steps`, so a resuming invocation can trust everything it reads — and `query_agent.py`, a real MCP client (official `mcp` SDK) that calls the CockroachDB Cloud Managed MCP Server's read-only SQL tool at runtime, exposed through `GET /api/v1/incidents/open` and the Gradio UI. The schema unifies transactional and vector memory in one CockroachDB store: `incidents` and `remediation_steps` under `SERIALIZABLE` isolation, `incident_embeddings` with a `service`-prefixed C-SPANN vector index.

### Challenges we ran into

**A demo that wasn't actually testing what it claimed.** The first version of the chaos-kill demo fired one alert to completion, then killed an unrelated idle process and fired a second alert — the "resume" only looked correct because the first run had already finished. I redesigned the remediation loop so each step has a real, interruptible execution window (`STEP_EXECUTION_SECONDS`), with the status committed to CockroachDB *before* execution starts — so a kill genuinely lands mid-step, and the fix is provable, not just claimed.

**A vector index that was provably used, over vectors that meant nothing.** The demo cluster's 40 embeddings were `synthetic-deterministic` — SHA-256 bytes normalised to a unit vector, which my own generator documents as *"deliberately NOT semantically meaningful — nearest-neighbour ordering is arbitrary."* `EXPLAIN` proved C-SPANN was being used; the benchmark proved it was fast; and the precedent it retrieved was a coin flip. Worse, Claude then wrote confident rationales over that precedent — *"identical symptoms... provides direct precedent"* — because the arbitrary draw happened to land on a plausible row. Measured properly: **precision@1 of 55%**, and even that was only duplicate summary strings hashing to identical vectors. I captured real Titan vectors into a committed fixture and replaced them — **precision@1 98%**, 39 of 40 nearest neighbours sharing the failure mode, symptom separation +0.1043 → +0.4585.

**Titan v2's dimension ceiling.** The initial schema assumed 1536-dim embeddings (an OpenAI-shaped assumption); Amazon Titan Text Embeddings V2 tops out at 1024. Caught before it became a runtime surprise — `VECTOR(1024)` throughout, with `embedding_dimensions` centralized in config so schema and embedding calls can't drift apart again.

**Cross-platform chaos.** The original kill script only worked on POSIX (`lsof` + `kill -9`). Rewritten on `psutil` so the same script — and a native `chaos_demo.ps1` for Windows — works everywhere the demo gets recorded.

### Accomplishments that we're proud of

- A resilience guarantee that's actually exercised end-to-end by CI — 88 unit tests pin the exact recovery semantics (read-before-write, transactional step checkpoints, re-execute-if-interrupted, claim-exactly-once-under-concurrency, resolve-after-final-step), and integration tests run that same contract against a real CockroachDB instance CI provisions on every push — one of them literally hard-killing a live orchestrator subprocess mid-step and asserting it resumes exactly once — not just asserted in a README
- One CockroachDB store doing double duty as both the transactional system of record and the vector index, with a single statement that filters on structured columns *and* ranks by `<->` distance
- Recovery proven under failure modes I don't control — including **AWS terminating the Lambda mid-step**, where nothing in the process gets a signal or a chance to checkpoint, and the next cold invocation still resumes that exact step exactly once — and **the deployed code being replaced mid-incident**, where the step is resumed on a build that did not exist when it began, with the durable CockroachDB row as the only thing bridging the two versions
- Tool claims a judge can verify **by querying my database rather than trusting my README**: every incident card renders provenance badges — the embedding and reasoning model, the C-SPANN recall rank and distance, the runtime, and whether a cold invocation resumed that step after a kill — each read from a durable column, with a legend naming which column. A step that fell back names no model, because it invoked none; a distance renders only beside the `embedding_model_id` that produced it, because distances from different vector spaces are not comparable
- Catching that my own headline CockroachDB integration wasn't running. The correlation query joined `incidents` in the same statement as the `<->` ordering, which made the planner fall back to `spans: FULL SCAN` — **results stayed correct, so nothing failed and nothing looked wrong**, while "Distributed Vector Indexing" was a load-bearing claim in this submission. It surfaced only because a scale benchmark produced the wrong *shape* of curve. Fixed with a CTE, and pinned by an integration test that reads the query plan, plus a second test that fails deliberately if a future CockroachDB version makes the workaround unnecessary
- A demo script honest enough to admit its own earlier bug and fix the root cause instead of hiding it

### What we learned

- "The demo shows recovery" and "the demo can only show recovery" are very different claims — the second one requires the interrupted step to genuinely be mid-flight when the kill lands, which means designing the execution window *first*, not bolting timing onto an existing flow
- CockroachDB's PostgreSQL-compatible vector support (`<->` distance, native `VECTOR` columns) means the correlation query is ordinary SQL — no separate vector store, no consistency gap to design around
- A single-write-path convention (one module, one set of write functions) is cheap to establish early and expensive to retrofit once other code has started writing directly to the tables
- **A green test suite proves a query is correct, never that it is using the index you think it is.** Only `EXPLAIN` does. A correctness test and a performance test can both pass while the feature you're claiming sits idle, which is why the query plan is now asserted rather than assumed
- **`EXPLAIN` proving the index is used does not prove the vectors in it mean anything.** One level deeper than the lesson above, and the same shape: a plan assertion, a latency curve and a green suite can all agree while the retrieval is noise. The only test that catches it measures *retrieval quality* — does the nearest neighbour share the failure mode? — against a baseline you can compute without the database. That test now exists (`tests/unit/test_precision_at_1.py`, `make precision-check`), which it did not when I first wrote this lesson down: the measurement had been made once by hand and then quoted in five documents, which is the same "trusted and unchecked" shape as the bug it describes
- **Benchmark against a baseline you deliberately made slow.** The full-scan comparison is what turned an absolute latency number — unfalsifiable on its own — into a *shape*, and the shape is what exposed the bug. Related: measure warm and cold connections separately, or a ~340 ms TLS handshake floor silently buries whatever you were trying to measure

### What's next for Continuum

- Real alert-source integrations (PagerDuty/Opsgenie webhook ingestion) in place of the synthetic stream
- Multi-region incident correlation via `REGIONAL BY ROW` incident tables
- ccloud CLI backup/replication verification as a standing pre-flight check, not just a chaos-demo gate
- Slack/Teams remediation-approval loop before a proposed step executes

### Built with

Python, FastAPI, psycopg 3, CockroachDB Cloud (Distributed Vector Indexing, Managed MCP Server), Amazon Bedrock (Titan Text Embeddings V2, Claude), AWS Lambda, Gradio, Hugging Face Spaces, structlog, pytest, Ruff

---

## CockroachDB Tools Used

| Tool | What the agent actually does with it |
| --- | --- |
| **Distributed Vector Indexing** | `incident_embeddings.embedding VECTOR(1024)` with a C-SPANN index prefixed by `service`; the Correlation Agent's live query filters by structured columns *and* ranks by `<->` distance in one round trip |
| **CockroachDB Cloud Managed MCP Server** | Read-only mode; `agents/query_agent.py` is the app's own MCP client (official `mcp` SDK, streamable HTTP) — `GET /api/v1/incidents/open` and the Gradio UI's "Ask via MCP" button run live questions ("open incidents and their current step") through the protocol at runtime, not only via Claude Code during development |

ccloud CLI was evaluated and intentionally not included — see ADR 004's resolution: two tools done well outscores three done thin.

## AWS Services Used

| Service | What the agent actually does with it |
| --- | --- |
| **AWS Lambda** | Orchestrator execution on the `python3.14` runtime; deliberately no provisioned concurrency, so every invocation proves state comes from CockroachDB, not warm process memory (ADR 002) |
| **Amazon Bedrock** | Titan Text Embeddings V2 for alert→vector (1024-dim, matching the `VECTOR(1024)` schema); Claude Sonnet 4.5 for remediation reasoning over matched precedent, with a deterministic precedent-replay fallback so the control flow demos even when throttled |
| **AWS SAM** | Infrastructure as code for the orchestrator function ([`infra/template.yaml`](../infra/template.yaml)) — the absence of `ProvisionedConcurrencyConfig` is a deliberate, reviewable artifact rather than a console setting |
| **AWS IAM** | Least privilege: the application's credentials are scoped to Bedrock model invocation only and cannot list, create, or delete AWS resources. Budget guardrails attach a deny-all policy at the spend ceiling — see [`COSTS.md`](COSTS.md) |
