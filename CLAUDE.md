# CLAUDE.md

Project context for Claude Code / agentic coding assistants working in this repo.

## What this project is
Continuum — an agentic incident-response system built for the CockroachDB × AWS Hackathon 2026. The single differentiating claim: the agent's memory (incident state + remediation progress) survives the agent process being killed mid-incident, because it lives in CockroachDB, not in local process memory.

**Current phase**: core build complete — recovery loop, dual memory model, explicit per-step `SERIALIZABLE` transactions + concurrency-safe exactly-once (ADR 009), best-effort Bedrock correlation, both CockroachDB tools, 100% unit coverage, and real (not stubbed) integration tests against a live cluster — including `tests/integration/test_chaos_kill_e2e.py`, which hard-kills a live orchestrator subprocess mid-step and asserts exactly-once cold recovery. The Hugging Face Space is deployed and live (`docs/DEPLOY.md`). Seeding no longer depends on live Bedrock: `make seed-data-offline` loads deterministic vectors with no AWS call, and `scripts/capture_seed_embeddings.py` + `seed_memory.py --from-fixture` load real Titan vectors captured once where Bedrock is reachable — so the AWS-side Bedrock quota issue (ADR 008) no longer blocks a populated demo. The latency-benchmark harness (`scripts/benchmark.py`, `make benchmark`) and the Lambda deploy runbook (`docs/DEPLOY.md`) are both in place, and `docs/BENCHMARKS.md` is populated with measured latencies against the live cluster.

**The Bedrock account quota clamp (ADR 008) was LIFTED on 2026-08-01** via an AWS Support eligibility review — `make probe-bedrock` returns OK for every candidate region × both models. **Both live Bedrock paths were then verified end to end on 2026-08-01**: `embed()` returns 1024 floats matching the schema, and `_propose_via_bedrock()` parses real Claude output correctly. That code is now proven, not merely unthrottled. Quotas remain *dynamic*, so re-probe immediately before recording rather than trusting a days-old green run — and note `make probe-bedrock` makes its **own** boto3 calls, so it proves account access only; verifying Continuum's own response handling means exercising the agents.

**The orchestrator is deployed and the recovery guarantee is proven on the real runtime** (2026-08-01): stack `continuum` in eu-central-1, `arn:aws:lambda:eu-central-1:504804196134:function:continuum-orchestrator`. Four cold `sam remote invoke` calls drove one incident 0 → 1 → 2 → `resolved`, each reporting `correlation_source`/`reasoning_source` of `bedrock`, so Bedrock and the vector search demonstrably ran inside Lambda under the function's own role. Cold start 1.71 s, 129 MB of 512 MB.

Deploy notes that cost time and will again: build from a **clean `git clone`**, never the working tree — `CodeUri: ../` packages the repo root, and a local `.venv`/`.mypy_cache` blows Lambda's 250 MB limit. `sam build` reads `infra/requirements-lambda.txt` (via `manifest` in `samconfig.toml`), *not* the root `requirements.txt`, which would ship Gradio and the dev toolchain into the function; `tests/unit/test_lambda_manifest.py` guards the two files against drift. Deploy with `--profile continuum-admin`; the default `continuum-bedrock` identity is Bedrock-invoke only and gets `AccessDenied` on CloudFormation by design. Run `make preflight-deploy` first — it checks all of this.

Remaining before submission: capture the judge-facing evidence runs into `assets/chaos-run/` (see `assets/README.md`), record the demo video (`submission/DEMO_SCRIPT.md`), and fill in the `submission/SUBMISSION.md` checklist end to end.

## Key Commands
```bash
make install            # pip install -r requirements.txt
make migrate            # apply infra/schema.sql to $COCKROACH_DATABASE_URL
make seed-data          # generate + load synthetic incidents (with Titan embeddings)
make seed-data-offline  # same, deterministic vectors, zero AWS calls
make run-api            # uvicorn api.main:app --port 8000
make run-ui             # python ui/app.py (Gradio)
make demo               # one remediation tick, in-process
make chaos-demo         # the kill-and-recover sequence — see submission/DEMO_SCRIPT.md
make probe-bedrock      # is live Bedrock open today? quotas are dynamic — run before recording
make benchmark          # latency benchmarks → docs/BENCHMARKS.md
make deploy             # sam build --use-container + sam deploy (docs/DEPLOY.md)
make lint               # ruff check . AND ruff format --check .  (both are CI-gated)
make format             # ruff format .  — rewrites
make typecheck          # mypy agents/ api/ observability/ config.py
make test               # pytest tests/unit tests/integration -v
make coverage           # pytest --cov=agents --cov=api --cov=observability --cov-report=term-missing
make load-test          # k6 read-path smoke (needs k6 + a running API)
make devpost-readme     # regenerate submission/DEVPOST_README.md from README.md
```
`tests/integration` requires a live CockroachDB at `$COCKROACH_DATABASE_URL` and skips gracefully without one; CI provides one via an ephemeral single-node container (`.github/workflows/ci.yml`), so `make test` locally without a cluster only runs the unit suite in practice.

## Architecture
Five agents, one write path (see `docs/ARCHITECTURE.md` for the full spec):

1. `orchestrator.py` — Lambda entrypoint; recovery-read-first control flow (ADR 002)
2. `correlation_agent.py` — Bedrock Titan embeddings + CockroachDB vector search
3. `remediation_agent.py` — Claude-on-Bedrock reasoning + deterministic precedent-replay fallback
4. `memory_agent.py` — the *only* module permitted to write `incidents`/`remediation_steps`; the orchestrator's per-step writes go through `checkpoint_step_start`/`checkpoint_step_done`, two explicit `SERIALIZABLE` transactions with the execution window between them (ADR 009)
5. `query_agent.py` — CockroachDB Managed MCP Server client (read-only), called by the app itself via `GET /api/v1/incidents/open` and the Gradio UI, not only by Claude Code during development (ADR 003)

CockroachDB tools used: **Distributed Vector Indexing** + **Managed MCP Server** — both load-bearing in the running app. ccloud CLI was evaluated and cut (ADR 004) rather than added as a thinner third integration. AWS: **Lambda** (orchestrator execution, no provisioned concurrency) + **Bedrock** (Titan embeddings, Claude reasoning).

## Non-negotiable constraints
- **All incident/alert/remediation data is synthetic.** Never introduce real company names, real infra, or anything resembling real credentials into seed data, code comments, or docs.
- **Every write to incident or remediation state goes through `agents/memory_agent.py`.** No other module should issue raw writes to `incidents` or `remediation_steps` — this single-write-path property is load-bearing for ADR 001/003, don't casually add a second one.
- **The orchestrator (`agents/orchestrator.py`) must not assume warm state.** Its first action on every invocation is a CockroachDB read to check for existing open incident state before doing anything else. Do not add any in-memory caching of incident state across invocations — that would silently break the resilience guarantee this project is built to prove.
- **The two-phase step checkpoint is load-bearing (ADR 009).** `checkpoint_step_start` commits the step as `executing` *before* the `time.sleep` execution window; `checkpoint_step_done` commits `executed` *after*. Keep them as two separate transactions with the sleep between them — a kill must land with `executing` durable. Keep the forward-step claim as `INSERT ... ON CONFLICT DO NOTHING`: switching it to `DO UPDATE` silently breaks exactly-once under concurrent invocations. Correlation/Bedrock in STEP 2 is deliberately wrapped in try/except (best-effort) so a Bedrock outage degrades to "no precedent" instead of aborting the incident before it's durable — don't make it fatal.
- **Code built during the Submission Period only** (June 30 – Aug 18, 2026, per hackathon rules) — no pre-existing code from any prior project may be ported in wholesale. General architectural *patterns* and personal conventions are fine to carry over; source code is not. This is an eligibility requirement, not a style preference.
- **`config.Settings` must tolerate unknown env vars** (`extra="ignore"`) — it is not the only consumer of the process environment (boto3 reads `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` itself). Reintroducing `extra="forbid"` breaks app startup for anyone with ordinary AWS credentials exported.

## Release & repo-sync discipline (do this on EVERY change, not at release time)

The repo is judged as a whole. Stale docs are read as carelessness, and they compound: a
version bumped in one file and not another is invisible until someone diffs them. Treat the
sweep below as part of the change, not as follow-up work.

**Run `make check-drift` before any commit that touched docs — it is CI-gated.**

`scripts/check_drift.py` mechanically verifies the things that kept going stale: version fields
agreeing, no date describing work as done before it happened, stated test and ADR counts matching
what actually exists, every relative link resolving, generated files current, and the Lambda
manifest in sync. It exists because asking for a manual sweep demonstrably did not work — a
release date four days in the future shipped on page one of the changelog, and a stale test count
survived several sweeps because each one checked whichever places came to mind.

Two rules that keep the gate worth having:

- **A new future date must be justified.** Deadlines are legitimately ahead of today, so they live
  in `KNOWN_FUTURE_DATES` with a reason. A date that isn't there fails, which forces the question
  "is this a deadline, or did I just claim something happened that hasn't?"
- **Never weaken a check to make it pass.** If it reports drift, the doc is wrong, not the checker
  — unless the checker is provably miscounting, in which case fix it and say so in the commit.

The checks below are what it covers, kept here because knowing *why* each one exists is what stops
someone deleting it later:
- **Version fields must agree**: `pyproject.toml` `version`, `api/main.py` `app.version`,
  `CHANGELOG.md` top section. If one moves, all move.
- **`requirements.txt` ↔ README badges ↔ Space frontmatter**: `gradio` must equal `sdk_version`
  in the README YAML frontmatter or the Space build fails. Version badges (FastAPI, psycopg,
  pytest, Python) must match the actual floors.
- **Counts stated in prose must be real**: test counts, ADR counts, coverage percentages,
  incident-seed counts, "N files" claims. Grep for them — they go stale silently.
- **Every path referenced in docs must exist.** Moving a file means grepping the whole repo for
  its old path, including `CLAUDE.md`, `Makefile`, CI workflows, and other docs — not just the
  README.
- **Claims must match code.** If behaviour changed, find the sentences asserting the old
  behaviour. `docs/ARCHITECTURE.md`, `submission/DEMO_SCRIPT.md`, and `submission/DEVPOST.md` assert
  a lot about the recovery path specifically.
- **Never let a placeholder ship as if finished.** `TBD`, "captured before submission", and
  tables describing artifacts that don't exist are worse than an honest "not yet" — a judge
  finds them first. Mark pending things pending, explicitly.

**Generated files — edit the source, never the output.** Each of these has exactly one definition;
regenerate rather than hand-editing, or the two copies drift and CI catches you late:

| Generated | Source | Regenerate with |
| --- | --- | --- |
| `submission/DEVPOST_README.md` | `README.md` | `make devpost-readme` — **CI fails if stale** (`--check`) |
| `assets/architecture/*-{dark,light}{,-16x9}.{svg,png}` | `*.mmd` | see `assets/architecture/README.md` |
| `assets/demo-cards/*-{dark,light}{,-native}.png` | `*.svg` | see `assets/demo-cards/README.md` |
| `assets/charts/chart-*-{dark,light}{,-16x9}.{svg,png}` | newest `assets/resilience-run/` | `make charts` |
| `assets/demo-voiceover/vo_*.mp3` + `assets/demo-video/continuum.srt` | `scripts/generate_demo_voiceover.py` | `make voiceover` |
| `docs/BENCHMARKS.md` | live cluster | `make benchmark` |
| `docs/RESILIENCE.md` | live cluster | `make resilience-bench` |

**`README.md` and `submission/DEVPOST_README.md` must never be out of sync — treat them as one
file with two renderings.** The mirror is what gets pasted into Devpost, so a stale one ships
wrong information to judges while the repo looks correct.

Three layers enforce this, in order of when they catch you:

1. **A `PostToolUse` hook** in `.claude/settings.json` runs `scripts/build_devpost_readme.py`
   automatically after any `Write`/`Edit` touching `README.md`. It is `async` and silent on
   success, so the mirror is usually already correct before you think about it.
2. **`python scripts/build_devpost_readme.py --check`** exits 1 if stale — run it before any
   commit that touched the README.
3. **CI** runs that same `--check`. It is the only gate that fails on a docs-only change, so a
   stale mirror is the most likely way to break a build that "shouldn't" have broken.

Never hand-edit `DEVPOST_README.md`; it is generated, and an edit there is destroyed on the next
regeneration. Change `README.md` and let the generator do the rest. **Any prose change to the
README — counts, dates, claims, new sections — is a change to both files.**

**Before tagging a release:**
1. `make lint && make typecheck && make test && make coverage` — all green, coverage above the gate.
   (`make lint` covers both `ruff check` and `ruff format --check`; CI gates them separately.)
2. `make devpost-readme` — the mirror must be current, or CI's `--check` step fails.
3. `CHANGELOG.md` has a section for the exact version being tagged; `release.yml` extracts release
   notes from it by regex, so the heading format `## [X.Y.Z]` is load-bearing.
4. **Tag the commit that is actually on `main`.** Tags were previously created and then orphaned
   by a rebase/amend that rewrote the commits underneath them — `git describe --tags` failed
   because no tag was an ancestor of `HEAD`. After tagging, verify:
   `git describe --tags` resolves, and `git log --oneline --decorate -5` shows the tag.
5. Push commits *and* tags: `git push origin main --follow-tags`.
6. Never rebase or amend a commit that a tag points at. If history must be rewritten, re-point the
   affected tags in the same operation and force-push them deliberately.

Commit subjects carry no version numbers — the tag and CHANGELOG carry the version.

## Style / conventions
- Python 3.14, psycopg 3 (psycopg2 has no 3.14 wheels); async where I/O-bound (DB calls, Bedrock calls, MCP calls)
- structlog JSON logging (`observability/structured_logger.py`) — no bare `print`
- Pydantic models for all structured data crossing an agent boundary
- **Ruff formats as well as lints** — `ruff format --check` is a CI gate. Run `make format` before committing; don't hand-align code against it. Ruff also lints `.ipynb`, so notebook cells follow the same rules (imports at the top of their cell)
- **Dependencies are floor-pinned with major-version caps** in `requirements.txt`. CI installs from that file on a clean runner, so an unbounded floor makes the next upstream major a surprise. Bump deliberately, run the suite, then commit — and never lift the `mcp<2` cap on a green unit suite alone
- **Model prompts live in `prompts/` as data**, loaded at import time by the owning agent. Import-time is deliberate: the Bedrock call site catches broadly and falls back, so a missing prompt caught there would be indistinguishable from an outage and would degrade silently
- Makefile targets are the source of truth for how to run anything — keep README Quick Start in sync with the Makefile, not the other way around
- ADRs go in `docs/adr/`, numbered sequentially, one decision per file
- Tests: mock at the module boundary (`patch("agents.x.boto3")`, `patch("agents.x.psycopg")`), never mock the class under test itself — see `tests/unit/` for the established pattern per agent

## Testing Strategy
- `tests/unit/` — one file per agent/module; all external I/O (psycopg, boto3, mcp SDK) mocked at the import boundary; coverage gate enforced at 90% (`--cov-fail-under=90` in CI)
- `tests/integration/test_recovery_e2e.py` — drives the resume + exactly-once contract against a live CockroachDB instance (the kill is injected as the durable `executing` state a real `chaos_kill.py` strike leaves; correlation/remediation mocked, memory agent and schema real). `test_forward_step_claim_is_exactly_once` proves the `ON CONFLICT` claim guard on a real cluster. Skips if `COCKROACH_DATABASE_URL` isn't set.
- `tests/integration/test_chaos_kill_e2e.py` — the literal version: spawns the orchestrator as a real uvicorn subprocess, hard-kills it mid-step with `scripts/chaos_kill.py` (a genuine `SIGKILL`/`TerminateProcess`), and asserts a cold restart resumes the interrupted step exactly once.
- `tests/integration/test_vector_index.py` — asserts via `EXPLAIN` that the correlation query actually uses the C-SPANN index. It did **not** for a long time: joining `incidents` in the same statement as the `<->` ordering made CockroachDB fall back to `spans: FULL SCAN`, so "Distributed Vector Indexing" was claimed but unexercised while results stayed correct. The CTE in `find_similar` is what restores it — don't inline it back. A second test fails deliberately if a future CockroachDB version plans the inlined JOIN through the index, so the workaround can't outlive its cause. 5 integration test functions across these 3 files.
- `tests/load/k6_smoke.js` — read-path smoke load, **not** run in CI (needs k6 + a live API). Deliberately never exercises `POST /alert`: that drives real state through the single write path, and racing the forward-step claim outside controlled conditions fabricates incidents rather than testing them.
- CI runs an ephemeral single-node CockroachDB container so the integration suite actually executes on every push, not just locally when a dev happens to have a cluster handy
- **A green unit suite is necessary but not sufficient for MCP or Bedrock changes.** Both are mocked at the import boundary, so the suite passes against a client that would fail against the real server. Those changes need a live round trip — this is exactly why `mcp` is pinned `<2` despite 2.0.0 being released.

## Deployment
- Region: **eu-central-1** — co-locates the Lambda with the CockroachDB Cloud cluster (ADR 007). Keep `AWS_REGION` / `config.py` defaults / `infra/template.yaml` in sync; a drift between them fails silently as a Bedrock access error, not a config error.
- Bedrock calls target a **separate** `BEDROCK_REGION` setting, not `AWS_REGION` (ADR 008). Keep it a separate setting — quotas are dynamic and account-level, and moving Bedrock without redeploying the Lambda is the whole point of the seam. **Its default is now `eu-central-1`, matching `AWS_REGION`** (ADR 008 addendum 3, 2026-08-01): the seam was introduced because an account-level clamp left eu-north-1 as the only region accepting calls, and once that clamp lifted nothing argued for the defaults differing. Same value, still two settings — so `make probe-bedrock` stays a pre-demo step and a closed region is a one-variable override. Both Bedrock paths degrade silently by design (no precedent / precedent-replay), so a throttled account *looks* fine while never touching Bedrock; the probe and the `reasoning_source` / `correlation_source` markers are how you tell which mode you're in.
- Lambda runtime: `python3.14` (`infra/template.yaml`) — matches the rest of the codebase; do not downgrade to chase an older SAM example.
- Demo UI: Gradio on Hugging Face Spaces (`docs/DEPLOY.md`), auto-synced on push to `main` (`.github/workflows/sync-to-hf-space.yml`)
- **The Hub rejects binary files over plain git** (Xet/LFS required), so the sync workflow strips PNG/MP4/MP3/etc onto a throwaway commit before force-pushing. Nothing the Space renders is binary — `README.md` embeds only SVGs — so this costs nothing. If you add a binary the *Space itself* needs, that assumption breaks and the workflow needs Xet, not another exclusion.

## Where things live
- Schema: `infra/schema.sql` — the dual transactional/vector memory model, read this before touching any DB code
- Architecture spec: `docs/ARCHITECTURE.md`. **Two diagrams, both source-of-truth `.mmd` files in `assets/architecture/`**: `architecture-diagram.mmd` (components — *what talks to what*) and `recovery-sequence.mmd` (the two-cold-invocation handoff — *what survives*). Neither is duplicated as an inline ```mermaid``` fence anywhere; `README.md` and `docs/ARCHITECTURE.md` embed the rendered SVGs. Edit the `.mmd` and re-render — never hand-edit an SVG/PNG.
- Demo script: `submission/DEMO_SCRIPT.md` — the kill-and-recover sequence is the thing being graded, treat changes to that flow as high-risk
- Judge-facing packet: `submission/` — `SUBMISSION.md` (rules checklist), `DEVPOST.md` (hackathon facts + judging-criteria mapping), `DEVPOST_README.md` (**generated** paste mirror of `README.md`), `DEMO_SCRIPT.md` (the recording script — owns the graded kill-and-recover flow), `COSTS.md`. These moved out of `docs/`; don't recreate them there.
- Judge-facing evidence: `assets/` — `assets/README.md` is the curated index and carries the capture plan for `assets/chaos-run/`
- Model prompts: `prompts/` — loaded at import time by the owning agent, deliberately (see `prompts/README.md`)

## When adding a CockroachDB or AWS integration
Ask first: does this tool have a real job in the demo, or is it being added to hit the "2+ tools" checklist? If the latter, don't add it — see ADR 004 for the reasoning. Decorative integrations hurt the Technical Implementation score more than they help eligibility.

## Hackathon Deadline & Judging Criteria
Submission due **August 18, 2026, 5 PM ET**. Judging (equally weighted): Agentic Memory Design, Technical Implementation, Real-World Impact, Production Readiness, Creativity & Originality. Full mapping: `submission/DEVPOST.md`.
