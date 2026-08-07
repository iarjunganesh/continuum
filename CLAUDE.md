# CLAUDE.md

Project context for Claude Code / agentic coding assistants working in this repo.

## What this project is
Continuum — an agentic incident-response system built for the CockroachDB × AWS Hackathon 2026. The single differentiating claim: the agent's memory (incident state + remediation progress) survives the agent process being killed mid-incident, because it lives in CockroachDB, not in local process memory.

**Current phase**: core build complete — recovery loop, dual memory model, explicit per-step `SERIALIZABLE` transactions + concurrency-safe exactly-once (ADR 009), best-effort Bedrock correlation, both CockroachDB tools, 100% unit coverage, and real (not stubbed) integration tests against a live cluster — including `tests/integration/test_chaos_kill_e2e.py`, which hard-kills a live orchestrator subprocess mid-step and asserts exactly-once cold recovery. The Hugging Face Space is deployed and live (`docs/DEPLOY.md`). **The demo cluster runs on real Titan vectors as of 2026-08-07**, captured into the committed fixture `data/synthetic/seed_embeddings.json` — so seeding is both honest and Bedrock-free (ADR 008 no longer blocks a populated demo). It had run on `synthetic-deterministic` hash vectors for a month, which `scripts/synthetic_vectors.py` documents as *"deliberately NOT semantically meaningful — nearest-neighbour ordering is arbitrary"*: measured **precision@1 55% → 98%** after the swap. **`make seed-data-offline` is for proving the table is populated, never for anything a reader will interpret as correlation** — prefer `seed_memory.py --from-fixture --replace-embeddings`. Note `--replace-embeddings` is required to overwrite: without it the insert is `ON CONFLICT DO NOTHING` and silently keeps whatever vectors are already there. The latency-benchmark harness (`scripts/benchmark.py`, `make benchmark`) and the Lambda deploy runbook (`docs/DEPLOY.md`) are both in place, and `docs/BENCHMARKS.md` is populated with measured latencies against the live cluster.

**The Bedrock account quota clamp (ADR 008) was LIFTED on 2026-08-01** via an AWS Support eligibility review — `make probe-bedrock` returns OK for every candidate region × both models. **Both live Bedrock paths were then verified end to end on 2026-08-01**: `embed()` returns 1024 floats matching the schema, and `_propose_via_bedrock()` parses real Claude output correctly. That code is now proven, not merely unthrottled. Quotas remain *dynamic*, so re-probe immediately before recording rather than trusting a days-old green run — and note `make probe-bedrock` makes its **own** boto3 calls, so it proves account access only; verifying Continuum's own response handling means exercising the agents.

**The orchestrator is deployed and the recovery guarantee is proven on the real runtime** (first proven 2026-08-01): stack `continuum` in eu-central-1, `arn:aws:lambda:eu-central-1:504804196134:function:continuum-orchestrator`. Four cold `sam remote invoke` calls drove one incident 0 → 1 → 2 → `resolved`, each reporting `correlation_source`/`reasoning_source` of `bedrock`, so Bedrock and the vector search demonstrably ran inside Lambda under the function's own role.

**Redeployed repeatedly on 2026-08-07** — `docs/DEPLOY.md` carries the log, which is the authority; don't restate hashes here, they go stale within the hour. Cold start **1719 ms init, 130 MB of 512 MB** was measured on `cfj/1z90…` and has not been re-sampled since. Before that day the function had gone **five days stale**, still running the 2026-08-02 build: it predated the KPI fix, `_stack_detail`, the Titan reseed and the current alert text. That matters beyond tidiness — Recording #1 resumes via `--via-lambda`, so filming against a stale function shows a Lambda behaving differently from the repo. **This is what ADR 010 exists to stop**; the manual rule stands for untagged builds: redeploy before recording, and check `CodeSha256` actually moved.

**Every failure mode in the Never-Miss table is now closed** (first 2026-08-02, re-proven on current code 2026-08-07): the last one, *deployment restart mid-incident*, is proven by `make deploy-restart-drill` — an incident held in a durable `executing` row while a real `sam build` + `sam deploy` swaps the function's code, then resumed exactly once on the new build (evidence `assets/deploy-restart-run/dba642ed/`, `cfj/1z90…` → `r8pbqNx1…`). The drill asserts `CodeSha256` actually moved; a no-op deploy would otherwise pass while proving nothing.

**Suite D in `docs/RESILIENCE.md` is generated, not written.** It renders from the newest `assets/deploy-restart-run/*/` evidence via `_suite_d()` in `scripts/resilience_bench.py`. It used to be typed into that file by hand, and the 2026-08-07 bench run silently deleted the entire section — the same trap that ate the staleness audit. Nothing hand-written may live in `docs/RESILIENCE.md`; add it to the generator instead.

Deploy notes that cost time and will again: build from a **clean `git clone`**, never the working tree — `CodeUri: ../` packages the repo root, and a local `.venv`/`.mypy_cache` blows Lambda's 250 MB limit. `sam build` reads `infra/requirements-lambda.txt` (via `manifest` in `samconfig.toml`), *not* the root `requirements.txt`, which would ship Gradio and the dev toolchain into the function; `tests/unit/test_lambda_manifest.py` guards the two files against drift. Deploy with `--profile continuum-admin`; the default `continuum-bedrock` identity is Bedrock-invoke only and gets `AccessDenied` on CloudFormation by design. **Setting `AWS_PROFILE` is not enough**: `.env` exports static `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` for that Bedrock-only user, and boto3 ranks static keys above the profile — so the profile is silently ignored and the failure arrives as an IAM `AccessDenied`, not a config error. Unset both in the shell before deploying or invoking. Run `make preflight-deploy` first — it checks all of this.

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
make export-memory      # snapshot incidents/steps/embeddings → data/snapshots/*.jsonl
make restore-memory SNAPSHOT=<path>   # put a snapshot back (idempotent, ON CONFLICT DO NOTHING)
make deploy-restart-drill CLONE_DIR=<clean checkout>  # redeploy under an open incident, prove the resume
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
- **The Cloud cluster serves the demo and nothing else.** `make resilience-bench`, `make benchmark`,
  `make chaos-capture`, `make load-test` and `pytest tests/integration` all write real incidents or
  drive sustained load — they go to `make local-cluster`, never to `$COCKROACH_DATABASE_URL` when
  that points at `*.cockroachlabs.cloud`. The cost is not Request Units (the whole project has used
  3.42M of a 50M/month allowance); it is that an N=200 bench left **665 incidents, 431 frozen in
  `remediating`**, on the cluster judges open. The `--allow-cloud-burn` guard in `resilience_bench.py`
  is a backstop, not permission. Published *latency* is the one exception and must come from Cloud.
  Full guidance: `docs/CLUSTER_OPS.md`.
- **Never set `CONTINUUM_UI_REFRESH_SECONDS` on the Hugging Face Space.** The timer costs ~50 RU per
  refresh — ~36K RU/hour *per open browser tab*, so one forgotten tab over a four-week judging period
  is ~24M RU, roughly half the monthly free allowance. Manual refresh is the default for this reason;
  if you enable it to record, unset it the same day.
- **A disabled cluster is not proof of overuse.** Free-tier capacity has a meter *and* a clock, and
  the platform returns the same "Request Unit limit" error for both. On 2026-08-03 a 30-day trial
  expired with 99.1% of the allowance unspent, and the error text caused a three-day misdiagnosis
  that reached `submission/COSTS.md`. **Read the billing page before writing down a cause.**
- **A UI badge reads a durable column, or it does not render.** The console's provenance badges (`⟲ resumed after kill`, `⌖ recalled #N of M`, embedding/reasoning model, `λ runtime`) each come from a field in `remediation_steps.detail` or `incident_embeddings.embedding_model` — never inferred from which code path exists, never defaulted, never prettified into something friendlier than the column says. Three consequences that look like bugs and are not: a step that fell back to precedent replay names **no** model (both Bedrock paths degrade silently, so an absent model id is the only signal the fallback ran); a `precedent_distance` renders **only** alongside the `embedding_model_id` that produced it (distances are not comparable across embedding models — this corpus's moved from ~1.40 to ~0.64 on reseed); and `runtime` comes from Lambda's own `AWS_LAMBDA_FUNCTION_NAME`, never from config, so a locally-run step cannot claim Lambda. `tests/unit/test_ui_kpis.py` pins all of it.
- **KPI tiles count the table; the card feed is paginated.** `FEED_LIMIT` caps the feed for layout only. Never derive the tiles from the feed rows — that made "durable in CockroachDB" a function of the CSS grid width and, worse, made the totals *drop* when unrelated rows were written.
- **`config.Settings` must tolerate unknown env vars** (`extra="ignore"`) — it is not the only consumer of the process environment (boto3 reads `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` itself). Reintroducing `extra="forbid"` breaks app startup for anyone with ordinary AWS credentials exported.

## Release & repo-sync discipline (do this on EVERY change, not at release time)

The repo is judged as a whole. Stale docs are read as carelessness, and they compound: a
version bumped in one file and not another is invisible until someone diffs them. Treat the
sweep below as part of the change, not as follow-up work.

**Run `make check-drift` before any commit that touched docs — it is CI-gated.**

`scripts/check_drift.py` mechanically verifies the things that kept going stale: version fields
agreeing, no date describing work as done before it happened, stated test and ADR counts matching
what actually exists, every relative link resolving, generated files current, the Lambda
manifest in sync, and the README's Project Structure naming every real path. It exists because asking for a manual sweep demonstrably did not work — a
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
- **The README's Project Structure must describe the repo that exists.** Every path it names must
  resolve, and every child of an enumerated directory (`agents/`, `scripts/`, `infra/`,
  `prompts/`, `assets/`, `data/`, `.github/workflows/`) must appear in the tree. Adding a script
  or an asset family is a change to the tree, in the same commit. This is checked mechanically
  because it failed silently for a long time: the tree was missing ten scripts, two asset
  families and the whole `data/` directory before anyone compared it to `ls`.

**The README is judged as one document, and it is the one most likely to go stale.** Sweep it
**twice** on any change that touches behaviour, structure, counts, or claims:

1. **Before committing to `main`** — walk the README top to bottom, section by section, not just
   the part you edited. The badge row (dependency floors — the release badge reads `latest` and
   links to `/releases/latest`, so it never needs bumping), What Is This, How It
   Works, the tool/service lists, Quick Start against the `Makefile`, Project Structure,
   Production & Quality, Load & Resilience. Then `make check-drift` and `make devpost-readme`.
2. **Before tagging** — again, because the version fields only become wrong *at* the tag, and a tag
   is the thing judges land on. The release badge is deliberately **not** one of them: it reads
   `latest` and links to `/releases/latest`, so GitHub resolves it and it cannot go stale. Do not
   reintroduce a hardcoded `release-vX.Y.Z` badge — it was wrong at exactly the moment a judge
   would see it, and `check_drift.py` never looked at it.

`submission/DEVPOST_README.md` is a rendering of the same file, so both sweeps cover it by
regenerating — never by editing it.

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

**A tag deploys the Lambda (ADR 010).** Everything below was already the standard; it is now the
thing standing between a bad commit and the live demo, so treat step 1 as a gate rather than a
formality. After pushing the tag, watch the **Deploy Orchestrator** run and confirm its summary
shows `CodeSha256` moving — a warning there means the tag shipped identical code.

1. `make lint && make typecheck && make test && make coverage` — all green, coverage above the gate.
   (`make lint` covers both `ruff check` and `ruff format --check`; CI gates them separately.)
2. `make check-drift`, then the README sweep above — top to bottom.
3. `make devpost-readme` — the mirror must be current, or CI's `--check` step fails.
4. `CHANGELOG.md` has a section for the exact version being tagged; `release.yml` extracts release
   notes from it by regex, so the heading format `## [X.Y.Z]` is load-bearing.
5. **Tag the commit that is actually on `main`.** Tags were previously created and then orphaned
   by a rebase/amend that rewrote the commits underneath them — `git describe --tags` failed
   because no tag was an ancestor of `HEAD`. After tagging, verify:
   `git describe --tags` resolves, and `git log --oneline --decorate -5` shows the tag.
6. Push commits *and* tags: `git push origin main --follow-tags`. **This deploys to AWS.**
7. Never rebase or amend a commit that a tag points at. If history must be rewritten, re-point the
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
- **The dev machine is Windows with PowerShell 7+ and has no `make` installed** (not in PowerShell, not in Git Bash). Targets remain the canonical description of *what* a step does, but anything written as a command a human will actually type — `README.md` Quick Start, `CONTRIBUTING.md`, `docs/DEPLOY.md`, and every runnable block in `submission/DEMO_SCRIPT.md` — must carry a PowerShell equivalent. Nearly every recipe is a single `python scripts/….py`; the two that cannot be translated are `chaos-demo` (backgrounding + `sleep`) and `deploy` (`$$VAR` expansion), which is why `scripts/chaos_demo.ps1` and the DEPLOY runbook exist. PowerShell has no inline `VAR=x command` prefix — env vars are set with `$env:VAR = "x"` on their own line, and unset with `Remove-Item Env:VAR`
- ADRs go in `docs/adr/`, numbered sequentially, one decision per file
- Tests: mock at the module boundary (`patch("agents.x.boto3")`, `patch("agents.x.psycopg")`), never mock the class under test itself — see `tests/unit/` for the established pattern per agent

## Testing Strategy
- `tests/unit/` — one file per agent/module; all external I/O (psycopg, boto3, mcp SDK) mocked at the import boundary; coverage gate enforced at 90% (`--cov-fail-under=90` in CI)
- `tests/integration/test_recovery_e2e.py` — drives the resume + exactly-once contract against a live CockroachDB instance (the kill is injected as the durable `executing` state a real `chaos_kill.py` strike leaves; correlation/remediation mocked, memory agent and schema real). `test_forward_step_claim_is_exactly_once` proves the `ON CONFLICT` claim guard on a real cluster. Skips if `COCKROACH_DATABASE_URL` isn't set.
- `tests/integration/test_chaos_kill_e2e.py` — the literal version: spawns the orchestrator as a real uvicorn subprocess, hard-kills it mid-step with `scripts/chaos_kill.py` (a genuine `SIGKILL`/`TerminateProcess`), and asserts a cold restart resumes the interrupted step exactly once.
- `tests/integration/test_vector_index.py` — asserts via `EXPLAIN` that the correlation query actually uses the C-SPANN index. It did **not** for a long time: joining `incidents` in the same statement as the `<->` ordering made CockroachDB fall back to `spans: FULL SCAN`, so "Distributed Vector Indexing" was claimed but unexercised while results stayed correct. The CTE in `find_similar` is what restores it — don't inline it back. A second test fails deliberately if a future CockroachDB version plans the inlined JOIN through the index, so the workaround can't outlive its cause.
- `tests/integration/test_snapshot_roundtrip.py` — exports, wipes and restores the memory layer against the real schema: rows and JSONB `detail` survive, a restored embedding still answers a `<->` search at distance ≈0, and the restore is idempotent. It exists because the export's own `_meta.note` advertised a restore command that did not exist, so the backup had never been restored. One test asserts that note still names a real command.
- 9 integration test functions across these 4 files.
- `tests/load/k6_smoke.js` — read-path smoke load, **not** run in CI (needs k6 + a live API). Deliberately never exercises `POST /alert`: that drives real state through the single write path, and racing the forward-step claim outside controlled conditions fabricates incidents rather than testing them.
- CI runs an ephemeral single-node CockroachDB container so the integration suite actually executes on every push, not just locally when a dev happens to have a cluster handy
- **A green unit suite is necessary but not sufficient for MCP or Bedrock changes.** Both are mocked at the import boundary, so the suite passes against a client that would fail against the real server. Those changes need a live round trip — this is exactly why `mcp` is pinned `<2` despite 2.0.0 being released.

## Deployment
- **Tagging deploys the Lambda.** `.github/workflows/deploy.yml` runs on any `v*.*.*` tag (ADR 010): OIDC role assumption, `sam build`, `sam deploy`, a `CodeSha256`-moved assertion, and an empty-payload invoke that proves the package imports without writing an incident. **`git push --follow-tags` therefore mutates AWS** — the pre-tag gates in the release checklist stop being a formality. It does *not* run on pushes to `main`, deliberately: redeploying during ordinary work would swap the code out from under a demo recording. The manual path in `docs/DEPLOY.md` still exists for untagged commits, `BedrockRegion` overrides and debugging.
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
