# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Nothing merged yet since `v0.7.1`.

**Remaining before submission** (tracked in `submission/SUBMISSION.md`):

- **Verify the live Bedrock paths end to end.** The ADR 008 quota clamp lifted 2026-08-06, but every correlation and remediation call in this project's history fell back silently — the real Titan and Claude response-handling code has never executed and is unproven rather than proven-good
- **Deploy the orchestrator to Lambda** (`make deploy`, `docs/DEPLOY.md`). Never done; no `samconfig.toml` yet, and it needs an admin AWS profile since the app credentials are Bedrock-invoke only
- **Capture the judge-facing evidence runs** into `assets/chaos-run/` — local kill and cold-Lambda, per the plan and numbered shot list in `assets/README.md`. Gated on the deploy above so the evidence shows the deployed system
- **Record the demo video** per `submission/DEMO_SCRIPT.md`, then replace the "Not yet recorded" row in the README's Live Demo table and re-link the YouTube badge
- **Complete the `submission/SUBMISSION.md` checklist** end to end
- **Decide on `mcp` 2.0.0.** Pinned `<2` deliberately — the unit suite mocks the SDK at the import boundary, so it would pass green against a client that fails against the real Managed MCP Server. Lifting the cap needs a live round trip

## [0.7.1] — 2026-08-01 — restore the Hugging Face Space build

### Fixed

- **The Hugging Face Space stopped building at `v0.7.0`, taking the functional demo URL offline.** That release raised the pydantic floor from `>=2.9` to `>=2.13,<3` as part of a general dependency-floor sweep. The Space builder does not install `requirements.txt` alone — it appends `gradio[oauth,mcp]==<sdk_version>`, and gradio's **`mcp` extra** pins `pydantic<=2.12.5,>=2.11.10`. The two ranges do not intersect, so the build died with `ResolutionImpossible` before the Space ever started. Nothing in this project needed 2.13; the real floor is `mcp` 1.29, which requires `pydantic>=2.12.0` on Python 3.14. Now pinned `pydantic>=2.12,<2.12.6`.

  Two things this is *not*: it is not fixable by moving `sdk_version`, because every gradio 6.x carries the same `mcp`-extra cap (verified across 6.15 → 6.22); and the upper bound is not the project's usual "cap the next major" convention but a deliberate compatibility ceiling, commented as such in `requirements.txt`. It is pinned rather than left open at `<3` so CI resolves the same pydantic the Space runs — an open cap would have CI testing 2.13 while the Space silently ran 2.12.5.

  The gap this exposes: `requirements.txt` is validated by CI, but the Space's *actual* install command is not, so a dependency edit can pass every gate and still take the demo down. Until that has a gate, treat a dependency change as unverified until the Space build goes green.

### Changed

- README's Pydantic badge corrected from `2.13 models` to `2.12`, and `submission/DEVPOST_README.md` regenerated to match.

## [0.7.0] — 2026-08-06 — judge-facing restructure, dependency hardening, tag history repaired

### Fixed

- **All seven release tags pointed at commits that no longer existed in `main`'s history.** A rebase/amend rewrote the commits underneath them, leaving every tag orphaned: `git describe --tags` failed outright with *"No tags can describe HEAD"*, `git log --decorate` showed no tags at all, and the GitHub Releases pages referenced unreachable objects. Each tag was re-pointed onto its identical-subject commit on `main` (mapping was 1:1 and unambiguous) preserving the original annotation messages and author dates, then force-pushed. `git describe` now resolves. A pre-tag checklist in `CLAUDE.md` encodes the verification so it can't silently recur
- **`mcp` was floor-pinned unbounded (`>=1.2`) while mcp 2.0.0 has shipped.** CI installs from `requirements.txt` on a clean runner, so the next run would have pulled a major-version bump into `agents/query_agent.py` — and because the unit suite mocks the SDK at the import boundary, it would have gone *green* against a client that fails against the real Managed MCP Server. Now capped `<2`; lifting it requires a live round trip, not a passing unit suite
- **Every dependency floor was stale by several major/minor releases** relative to what the project actually runs on (e.g. `fastapi>=0.115` against 0.139 installed). All floors raised to tested versions with major-version caps, so a clean CI install can no longer drift from the development environment
- **`README.md` advertised artifacts that did not exist** — a Screenshots table describing five screenshots with none in the repo, and a `youtu.be/TBD` demo-video link. Both replaced with explicit, honest pending-state notes
- **The Hugging Face Space sync would have broken on the binaries this release adds.** The Hub rejects binary files pushed over plain git — they must go through [Xet/LFS](https://huggingface.co/docs/hub/xet) — so the new diagram and brand-card PNGs failed the pre-receive hook (`Your push was rejected because it contains binary files`) and the Space stopped updating. The Hub's pre-receive hook scans **every commit in the push**, not just the tip, so stripping binaries in a new commit doesn't help — the blobs still exist in the parents. The sync workflow now publishes a single **orphan** commit containing the current tree minus binaries (PNG/JPG/GIF/WEBP/MP4/MOV/MP3/WAV/PDF/ZIP). The Space is a deployment target, not a mirror of history — it needs the files, not the commits — and this is immune to any binary that has ever existed anywhere in the repo's past. Nothing the Space renders is binary — `README.md` embeds only SVGs, which are text and push fine — so the Space is unaffected and the binaries stay on GitHub where the judge-facing evidence belongs. This would otherwise have become a hard blocker once `assets/demo-video/continuum.mp4` lands
- **`docs/DEPLOY.md` still documented `sdk_version: 6.19.0`** against the actual `6.22.0`; corrected, and reworded to state the invariant (it must equal the `gradio` floor in `requirements.txt`, or the Space build fails) rather than restate a number that goes stale

### Added

- **Brand cards** (`assets/demo-cards/`) — hero banner and closing sign-off, dark and light, authored as SVG (the single source of truth) with eight rendered PNGs: native size (1000×410 banner, 1000×450 sign-off) plus letterboxed 16:9 (1920×1080) video cards. The design carries the argument: the banner's infinity loop is **severed** by an orange kill stroke, the sign-off's loop is **whole** with only the terminal dot left — problem and payoff. `banner.html` / `signoff.html` are thin theme-aware export wrappers (`?theme=`, `?native=`), not a second implementation. Both cards are now embedded in `README.md` via theme-matched `<picture>` elements
- **Two rendered diagrams** (`assets/architecture/`), deliberately separate because they answer different questions: `architecture-diagram` (components — *what talks to what*) and `recovery-sequence` (the two-cold-invocation handoff over time — *what survives*). Each ships dark/light SVG for embedding, a PNG at natural aspect, and a 1920×1080 letterboxed 16:9 PNG as a pre-built demo-video flash-cut asset, generated from `.mmd` source via `mermaid-cli` with shared per-theme config files
- **Neither diagram is duplicated as an inline ```mermaid``` fence any more.** `README.md` and `docs/ARCHITECTURE.md` now embed the rendered SVGs through theme-matched `<picture>` elements wrapped in click-to-enlarge links, so the `.mmd` files are the only definitions. The brand theming (CockroachDB purple, AWS orange, dashed subgraph borders) only exists in the `mermaid-cli` render — GitHub's built-in renderer applies its own theme and ignores the config file, so a fence could never have looked right
- **`submission/DEVPOST_README.md`** — a paste-safe mirror of `README.md` with every relative link and image rewritten to absolute `github.com` / `raw.githubusercontent.com` URLs, so pasting it into Devpost's description field leaves every link and image resolving. **Generated, never hand-edited**: `scripts/build_devpost_readme.py` (`make devpost-readme`) builds it and `--check` verifies it, which CI runs — editing the README without regenerating now fails the build instead of silently shipping a stale submission doc
- **`ruff format` is now a gate**, not just a convention: `ruff format --check` runs in CI and in `make lint`, with `make format` to rewrite. The codebase was reformatted once (28 files) so the claim is true rather than aspirational
- **`submission/` — the judge-facing packet.** `SUBMISSION.md` and `DEVPOST.md` moved out of `docs/` (history preserved), joined by `DEMO_SCRIPT.md` (the full recording script and production guide, absorbing the former `docs/DEMO_RUNBOOK.md`) and `COSTS.md` (per-incident cost model, actual spend to date, guardrails, scaling estimate)
- **`assets/` — the judge-facing evidence tree.** `assets/README.md` is a curated index carrying the capture plan for two chaos runs (local kill and cold Lambda), the numbered screenshot list, and an explicit note on how Bedrock's silent degradation will be disclosed rather than hidden. Subtrees for `architecture/`, `chaos-run/`, `demo-cards/`, `demo-video/`, each with its own README
- **`assets/architecture/architecture-diagram.mmd`** — the README's mermaid diagram extracted to a source-of-truth file, with brand-themed render instructions for `mermaid-cli`
- **Mypy type gate** in CI and as `make typecheck`, matching the existing Ruff gate. One genuine finding: `Settings()` reads its required `cockroach_database_url` from the environment, which mypy can't model — narrowed to a documented `type: ignore[call-arg]` rather than given a default that would let the app start pointed at nothing
- **`prompts/`** — the remediation reasoning prompt externalised from `agents/remediation_agent.py` as data. Loaded at *import* time deliberately: `propose_next_step` wraps its Bedrock call in a broad `except Exception` that falls back to precedent-replay, so a missing prompt file caught there would be indistinguishable from a Bedrock outage and would degrade silently
- **`tests/load/k6_smoke.js`** — read-path smoke load against `/health` and the MCP-backed `/incidents/open`. Deliberately does not exercise `POST /alert`: that drives real state through the single write path, and hammering it would fabricate incidents and race the forward-step claim outside the controlled conditions the integration suite asserts it under
- **`notebooks/DEMO_RUNBOOK.ipynb` + `notebooks/README.md`** — an interactive walkthrough of the kill-and-recover sequence runnable against any reachable deployment, so the recovery guarantee can be verified without cloning
- **Release & repo-sync discipline** in `CLAUDE.md`: a per-commit drift sweep (version fields, badge/frontmatter agreement, stated counts, path references, a ban on placeholders shipping as finished) and a pre-tag checklist

### Changed

- **`docs/DEMO_RUNBOOK.md` removed**, its content folded into `submission/DEMO_SCRIPT.md` so the graded kill-and-recover flow has exactly one source of truth instead of a runbook and a production script that could drift apart. All live references repointed
- **`SECURITY.md` substantially expanded** — supported-version policy, deployment-secret locations, least-privilege posture (read-only MCP, single write path, Bedrock-only IAM scope), the empirically-grounded TLS rationale, private-advisory reporting link, and four newly documented known limitations including that prompt injection via alert text is out of scope while alerts are operator-authored
- **`CONTRIBUTING.md` substantially expanded** — quality-gate commands, testing conventions, an explicit "things that will get a change rejected" list covering every load-bearing invariant with its ADR, and a warning that a green unit suite is not sufficient for MCP or Bedrock changes since both are mocked at the boundary
- **README badges regrouped into six labelled rows** (status · CockroachDB core · AWS · agent runtime · quality gates · hosting) with explicit version numbers throughout, and the project-structure tree updated for the new layout
- **Dependencies upgraded**: FastAPI 0.141.1, uvicorn 0.52.0, boto3 1.43.61, Gradio 6.22.0, Ruff 0.16.1, plus mypy 2.3.0 added. The Gradio bump is mirrored in the README frontmatter `sdk_version`, which is what the Hugging Face Space actually builds against
- **ADR 008 outcome:** the account-level Bedrock quota clamp was **lifted on 2026-08-06** following an AWS Support eligibility review. `make probe-bedrock` now returns OK for every candidate region and both models, with no config change needed. Two caveats recorded in `CLAUDE.md`: quotas remain dynamic, so re-probe before recording; and the live Bedrock path has never actually executed in this project's history, so that code is unproven rather than proven-good
- Cross-repo references to unrelated sibling projects removed from `CLAUDE.md`

## [0.6.0] — 2026-07-08 — Bedrock/Lambda deep audit: fail-fast clients, probed region default, Lambda-driven demo

### Fixed

- **The default Bedrock region pointed at an endpoint known to throttle.** `config.py`, `infra/template.yaml` and the `docs/DEPLOY.md` deploy command all still defaulted to eu-west-1 — contradicted by the 2026-07-07 probe recorded in `.env.example`. All defaults now align on eu-north-1, and an ADR 008 addendum records the 2026-07-08 probe result (`scripts/probe_bedrock.py`): **every** region throttles **every** model on the first call — Titan "Too many requests", Claude *and first-party Nova* "Too many tokens per day" — i.e. an account-level dynamic quota clamp that neither model choice, region choice, nor promotional credits routes around; only an AWS Support escalation or account usage history lifts it
- **Bedrock clients ran on botocore defaults** (60s read timeout, backoff retries) — one throttled/hung call could consume the entire Lambda invocation budget and kill the function mid-step *organically*, making the recorded demo nondeterministic. Both `bedrock-runtime` clients now set `connect_timeout=5`, `read_timeout=15`, standard-mode retries capped at 2 attempts, and the Lambda `Timeout` went 30s → 60s with the per-step budget math documented in the template
- **The Gradio "Ask via MCP" panel swallowed the real MCP error.** The MCP client raises from inside an anyio `TaskGroup`, so a failure surfaced on the Space as the useless `unhandled errors in a TaskGroup (1 sub-exception)`. The handler now unwraps `ExceptionGroup`s recursively to their leaf errors (e.g. `McpError: executing select query: unauthorized`) and short-circuits with an actionable setup message when the key/cluster id aren't configured. Exercising the fixed path against the live server also pinned the real failure mode — a service-account key *authenticates* but every query returns `unauthorized` until the account holds the **Cluster Operator** role on the cluster — now documented in `docs/DEPLOY.md` alongside the previously-undocumented `COCKROACH_MCP_CLUSTER_ID` Space secret
- **Sharpened the TLS guidance across `.env.example`, `docs/DEPLOY.md` and `infra/template.yaml`.** `sslmode=require` stays the documented choice (encrypts, no CA file, works in every fresh container — acceptable for synthetic data, ADR 005), but the *why* is now empirically grounded: this cluster's cert is actually publicly-trusted (Let's Encrypt, verified 2026-07-08), yet `sslmode=verify-full&sslrootcert=system` still fails through psycopg/libpq (`certificate verify failed`, tested on libpq 18) because libpq's `system` CA store is empty/unresolved on many platforms. The docs now explicitly warn against `verify-full&sslrootcert=system` and note it's the cause of that exact error, so the guidance doesn't get "corrected" back to a string that doesn't work

### Added

- **`scripts/probe_bedrock.py` / `make probe-bedrock`** — one InvokeModel + one Converse per candidate region, retries disabled. Run before recording: both Bedrock paths degrade silently by design (no precedent / precedent-replay), so a fully throttled account *looks* healthy while never touching Bedrock — the probe tells you which mode you're demoing in
- **`scripts/demo_run.py --tick --via-lambda`** — drives an alert tick through the deployed `continuum-orchestrator` function, making the runbook's "a fresh Lambda invocation starts cold" literal instead of simulated; first real consumer of `LAMBDA_FUNCTION_NAME` (previously dead config)
- **`make deploy`** — `sam build --use-container` + `sam deploy`; the container build is required when building on Windows/macOS because `psycopg[binary]`/`pydantic-core` ship compiled wheels and a host-platform build crashes on Lambda's Linux runtime with import errors (now documented in `docs/DEPLOY.md`)
- **`docs/DEMO_READINESS_CHECKLIST.md`** — P0/P1 winner-level demo checklist, audited against actual repo state; biggest open blockers called out (no recorded video, Space can't self-trigger an incident, `docs/BENCHMARKS.md` never populated)
- `infra/__init__.py` so `infra.lambda_handler` imports as a regular package rather than relying on namespace-package resolution

### Changed

- `docs/DEMO_RUNBOOK.md` pre-flight now starts with `make probe-bedrock`, and the recovery beat documents both drivers: restart-and-retick `--via-api` (what `chaos_demo.ps1` does) or `--via-lambda` for a real cold Lambda invocation

## [0.5.0] — 2026-07-07 — MCP query path restored; benchmarks, real-kill test, Bedrock-free seeding

### Fixed

- **QueryAgent now speaks the Managed MCP Server's current contract.** The server scopes each session to a cluster via an `mcp-cluster-id` header and requires a `database` argument per query; without them every call failed (`401 Unauthorized` unauthenticated, `cluster_id not provided` once a key was configured). New settings `COCKROACH_MCP_CLUSTER_ID` / `COCKROACH_MCP_DATABASE`; constructor args passed as explicit blanks stay blank so unit tests remain hermetic whatever the local `.env` holds. Verified end to end against the live server (auth, session negotiation, query dispatch)
- **`.env.example` realigned with `.env`** after significant drift: adds the Managed MCP service-account block (endpoint, cluster id, database, API key — with the console steps for creating the key), replaces the now-false "eu-west-1 has full default quota" Bedrock claim with probe-first guidance (2026-07-07: eu-west-1, eu-central-1 and us-east-1 all throttle Titan on this account; eu-north-1 works at a low per-minute rate), and warns that Bedrock retires old model versions (`eu.anthropic.claude-3-5-sonnet-20241022-v2:0` — found pinned in a stale `.env` — now returns "invalid model identifier")

### Added

- **`.mcp.json`** — project-scoped CockroachDB Cloud MCP server config for Claude Code (streamable HTTP, cluster-scoped via the `mcp-cluster-id` header, Bearer auth via `${COCKROACH_MCP_API_KEY}` environment expansion, so no secret lives in the committed file)
- **Lambda deploy runbook** in `docs/DEPLOY.md`
- **Bedrock-free seeding** so the demo Space can be populated without the throttled Bedrock account (ADR 008): `make seed-data-offline` / `.\scripts\migrate_and_seed.ps1 -Offline` seed deterministic synthetic vectors (`scripts/synthetic_vectors.py`) with no AWS call, and `scripts/capture_seed_embeddings.py` + `seed_memory.py --from-fixture` load real Titan vectors captured once where Bedrock is reachable
- **Recovery sequence diagram** and a typical-vs-Continuum comparison table in `docs/ARCHITECTURE.md`, making the two-cold-invocation handoff through durable CockroachDB state visible at a glance

### Changed

- **Sharpened the hero positioning** across the README, the Hugging Face Space (`ui/app.py`), and the DEVPOST elevator pitch to lead with the concrete payoff — *resumes the exact step it was killed on, because its memory lives in CockroachDB, not the process* — instead of the more abstract earlier tagline
- **Repo-wide documentation alignment pass.** Synced stale version fields (`api/main.py`, `pyproject.toml` → `0.4.0`); corrected the integration-test count (2 → 3) and surfaced the real-`SIGKILL` `test_chaos_kill_e2e.py` in the README and DEVPOST test-integrity claims; fixed the `docs/ARCHITECTURE.md` §4.1 vector-index DDL to match `infra/schema.sql` (always `service`-prefixed, `embedding_model` column, `service`-only filter); standardized the judging criterion name to **Production Readiness**; aligned the `schema.sql` recovery-query comment with the actual latest-step query; and removed cross-project references from `docs/SUBMISSION.md`
- **Latency benchmarks** (`scripts/benchmark.py`, `make benchmark`, `docs/BENCHMARKS.md`): p50/p95/p99 for recovery read, per-step transaction commits, C-SPANN vector search, and the full cold-resume path — against a live cluster, no Bedrock dependency
- **Real-kill chaos integration test** (`tests/integration/test_chaos_kill_e2e.py`): spawns the orchestrator as a uvicorn subprocess, hard-kills it mid-step with `scripts/chaos_kill.py` (real SIGKILL/TerminateProcess), and asserts a cold restart resumes the interrupted step exactly-once from CockroachDB — the literal process-kill path that `test_recovery_e2e.py` only simulated with a SQL UPDATE. Shared integration fixtures moved to `tests/integration/conftest.py`

## [0.4.0] — 2026-07-06 — claims-vs-code integrity: real transactions, exactly-once, Bedrock-hardened recovery

### Added

- **Explicit per-step transaction boundaries (ADR 009).** The orchestrator's STEP 3 now goes through `MemoryAgent.checkpoint_step_start` / `checkpoint_step_done`, each an explicit `with conn.transaction()` block (CockroachDB `SERIALIZABLE`), with the `time.sleep` execution window between them so a kill still commits `executing` and nothing else. Makes the "transactional memory" claim literally true, not just per-statement autocommit
- **Concurrency-safe exactly-once forward claim (ADR 009).** A new step is claimed with `INSERT ... ON CONFLICT (incident_id, step_index) DO NOTHING`; a racing invocation that loses the claim skips execution instead of double-running the step. `checkpoint_step_done` guards its transition with `AND status = 'executing'`. Proven on a real cluster by `tests/integration/test_recovery_e2e.py::test_forward_step_claim_is_exactly_once`
- **Best-effort correlation.** Orchestrator STEP 2 (`embed` + `find_similar`) is wrapped in try/except — a throttled/misconfigured Bedrock endpoint now degrades to "no precedent" (remediation falls back to `page_on_call_engineer`) instead of throwing before the incident is durable. Removes the single point of failure that a red Bedrock endpoint (ADR 008's 0-quota risk) posed to the whole recovery demo

### Changed

- Aligned docs/claims to the code after auditing the whole repo: corrected "6 ADRs" → 9, unit-test count → 46 (100% measured coverage against the 90% gate), and the ARCHITECTURE.md §3 recovery sequence (it inaccurately showed a killed step being *skipped*; the code re-runs the interrupted step). `docs/DEMO_RUNBOOK.md` 0:20 now uses `--via-api` (a bare `--tick` runs in-process, leaving nothing for `chaos_kill.py` to strike) and notes `make chaos-demo` is POSIX-only

### Removed

- `MemoryAgent.log_step` / `set_step_status` — dead code once STEP 3 moved to the transactional checkpoints; their docstrings described a mechanism the orchestrator no longer used

## [0.3.2] — 2026-07-05 — Bedrock region split; Anthropic use-case form + EULA agreement resolved

### Fixed
- **eu-central-1 has a `0`, non-adjustable Bedrock quota on this account for every model** (Titan Embed V2 and every Claude Sonnet variant, both on-demand and cross-region) — confirmed via `aws service-quotas list-service-quotas`, not assumed. `seed_memory.py`'s single-transaction seeding was failing silently on the first embedding call and rolling back every record. Added `bedrock_region` (`BEDROCK_REGION`, default `eu-west-1`) used only by the `bedrock-runtime` clients in `correlation_agent.py`/`remediation_agent.py`; `aws_region`/Lambda/CockroachDB stay in eu-central-1 (ADR 007 untouched, split documented in ADR 008)
- **Anthropic models required a one-time, account-wide "use case details" form** (`agreementAvailability: NOT_AVAILABLE` on every Claude version checked, not just 4.5) before any Anthropic model could be invoked — submitted via `aws bedrock put-use-case-for-model-access`, followed by `create-foundation-model-agreement` to accept Claude Sonnet 4.5's EULA specifically. Confirmed via `get-foundation-model-availability`: `agreementAvailability` now `AVAILABLE`
- `seed_memory.py` now retries `ThrottlingException` with exponential backoff (5s → 160s over 6 attempts) and commits per record instead of one final commit for the whole file, so a mid-run throttle no longer discards already-seeded rows

### Known issue (not code — AWS account state)
- Even with the above fixed, this brand-new AWS account still hits sustained `ThrottlingException`/`"Too many tokens per day"` on both Titan Embed V2 and Claude Sonnet 4.5 that a 6-retry/~5-minute backoff didn't clear — an automated new-account trust ramp that published Service Quotas values don't reflect. No CLI lever for this; expect it to loosen with time/usage. `remediation_agent.py`'s deterministic precedent-replay fallback keeps the app functional in the meantime

## [0.3.1] — 2026-07-05 — Space actually boots; Windows setup script; scripts/*.py import fix

### Fixed
- **The 0.3.0 Space still didn't boot**: Gradio's launch-time analytics telemetry compares the app's theme against its built-in themes; built-in themes use `Font` objects for `font`/`font_mono` while ours used plain strings, and Gradio's own `Font.__eq__` doesn't guard against comparing to a non-`Font` — crashing with `AttributeError: 'str' object has no attribute 'name'` whenever analytics is enabled (the Spaces default). Fixed via `analytics_enabled=False` on the `Blocks` constructor, which also means this read-only demo doesn't phone telemetry home
- **`scripts/seed_memory.py`, `demo_run.py`, and `chaos_kill.py` had the same subdir-import bug as `ui/app.py`** (fixed for that file in 0.3.0, missed here): running `python scripts/x.py` puts `scripts/` — not the repo root — on `sys.path`, so `from agents…`/`from config…`/`from observability…` raised `ModuleNotFoundError`. This meant `make seed-data`, `make demo`, and `make chaos-demo` — the actual kill-and-recover sequence `docs/DEMO_RUNBOOK.md` calls the thing being graded — never worked via their documented entrypoints, only discovered while running the Windows seed script end to end for the first time. All three now bootstrap the repo root the same way `ui/app.py` does
- `seed_memory.py` paces its Bedrock embedding calls (1s between records) — a tight back-to-back loop of 40 calls was hitting `ThrottlingException` immediately

### Added
- `scripts/migrate_and_seed.ps1` — Windows equivalent of `make migrate` + `make seed-data` (no `make` on Windows), matching the existing `chaos_demo.ps1` pattern. Checks `COCKROACH_DATABASE_URL` and (unless `-SkipSeed`) AWS credentials up front with a clear message instead of a bare traceback, and checks `$LASTEXITCODE` after every external `python` call — `$ErrorActionPreference = "Stop"` only covers PowerShell cmdlets/terminating errors, not external command exit codes, so a failed step would otherwise print a traceback and the script would carry on and report success anyway (caught by testing the schema step against an unreachable DB)

### Changed
- Space pins **Python 3.14** (`python_version: "3.14"` in README frontmatter), matching CI (`python-version: "3.14"`) and local dev — previously unset, so the Space picked whatever Hugging Face's own default was (observed: 3.13) rather than the project's actual target
- CockroachDB Cloud TLS guidance corrected to `sslmode=require`: `sslrootcert=system` doesn't work for CockroachDB Cloud, since its clusters use a cluster-specific CA rather than one chained to a public root — `verify-full` fails there with `certificate verify failed` even once the root-cert-file-missing error is resolved. `require` encrypts without needing any CA file, an acceptable trade-off since Continuum only ever stores synthetic data (ADR 005) and this connection only ever reaches CockroachDB Cloud's own endpoint

## [0.3.0] — 2026-07-05 — demo Space redesigned as a live incident-memory console

### Added
- **`ui/app.py` rebuilt into a dark, NOC-style incident console** (from a single Dataframe). The resilience story is now visible on screen, not only in the video:
  - **Recovery timeline** drill-down — pick an incident and replay its `remediation_steps` log; the step stuck in `executing` pulses and is flagged *"the process died here — the next cold invocation resumes at exactly this step"*
  - **Resilience banner** that reads the live count of in-flight (`executing`) steps and states the resume guarantee in plain terms
  - **KPI tiles** (Open · In-flight now · Resolved · Steps committed) using the accessible status palette (icon + label, never colour alone)
  - **Incident cards** with a per-incident mini step-tracker, and `gr.Timer` auto-refresh (5s) so the feed stays live during the demo
  - Still read-only: direct psycopg for the feed, `query_agent` (MCP) for the "Ask via MCP" panel — `memory_agent.py` remains the only write path
- Static preview of the console for design review (rendered from the app's own functions over synthetic incidents)

### Changed
- Space now pins **Gradio 6** (`sdk_version: 6.19.0` in README frontmatter; `requirements.txt` floor `gradio>=6.0`), matching the development environment
- README Screenshots / Demo-UI wording updated to describe the console + recovery timeline rather than a bare incident feed
- `docs/DEPLOY.md` and `docs/DEMO_RUNBOOK.md` updated to reflect the new UI (recovery-timeline drill-down as the demo's visual proof) and the Gradio-6 pin

### Fixed
- **HF Space build was broken in 0.2.0**: `app_file: ui/app.py` is in a subdirectory, so running it as a script put `ui/` (not the repo root) on `sys.path`, and `from agents…`/`from config…` failed with `ModuleNotFoundError`. `ui/app.py` now bootstraps the repo root onto `sys.path` before those imports
- Gradio 5→6 API move: `css`/`theme`/`js` relocated from `Blocks()` to `launch()`. The stylesheet is now injected as a `<style>` component (renders on any version) and `launch()` kwargs are guarded by a signature check, so the app can't crash on a version mismatch

## [0.2.0] — 2026-07-05 — working core, MCP hardening, 100% coverage

### Added
- Real Amazon Bedrock wiring: Titan Text Embeddings V2 (1024-dim, matching `VECTOR(1024)` schema) in the Correlation Agent; Claude-on-Bedrock reasoning with deterministic precedent-replay fallback in the Remediation Agent
- Genuinely interruptible remediation loop: each invocation drives one step through `proposed → executing → executed` with a simulated execution window; a kill mid-step leaves `executing` durably in CockroachDB and the next cold invocation re-runs that exact step
- Cross-platform `chaos_kill.py` (psutil) + `scripts/chaos_demo.ps1` for Windows; fixed `make chaos-demo` to actually kill the process doing the work
- Seeded historical incidents now include their remediation step history, so precedent replay has real precedent
- CI quality gate (`.github/workflows/ci.yml`): Ruff → pytest → coverage → Codecov
- `pyproject.toml` (Python 3.14, Ruff, pytest/coverage config)
- **`agents/query_agent.py`** — a real client of the CockroachDB Cloud Managed MCP Server (official `mcp` SDK, streamable HTTP), called by the running app itself via `GET /api/v1/incidents/open` and the Gradio UI's "Ask via MCP" panel, not only by Claude Code during development (ADR 003 amended). This and Distributed Vector Indexing are Continuum's two CockroachDB tools; ccloud CLI was evaluated and cut (ADR 004 resolution, ADR 006)
- Real integration test (`tests/integration/test_recovery_e2e.py`) exercising the actual kill-and-recover cycle against a live CockroachDB instance — previously a stub that always skipped itself
- CI now provisions an ephemeral single-node CockroachDB container so the integration suite runs on every push, not only when a developer happens to have a cluster handy
- Unit test suite grew from 5 to 42 tests (one file per agent/module: memory, correlation, remediation, query agent, API, observability) — coverage 60% → 100%; CI gate raised 60% → 90%
- `.github/workflows/release.yml` — tags matching `v*.*.*` cut a GitHub Release with notes pulled from this file
- `docs/adr/007-eu-central-1-region.md` — documents the deployment region and cross-region inference profile choice
- Project-level `.claude/settings.json` — safe read-only + build/test command allowlist, ruff-autofix-on-edit hook

### Changed
- Python 3.12 → 3.14; psycopg2 → psycopg 3 (no cp314 wheels for psycopg2); dependencies switched to floor pins that resolve to latest
- Schema: `VECTOR(1536)` → `VECTOR(1024)` (Titan v2's max output dimension — 1536 was unsatisfiable)
- README rebuilt to submission grade: logo, CI/coverage badges, brand-colored Mermaid architecture, recovery-timeline table, tech-stack badge table, CI/CD + screenshots sections
- AWS region `us-east-1` → `eu-central-1`; Bedrock reasoning model to `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` (EU cross-region inference profile) — kept in sync across `.env.example`, `config.py`, `infra/template.yaml` (ADR 007)
- `infra/template.yaml` Lambda runtime `python3.12` → `python3.14`, matching the rest of the codebase
- CLAUDE.md expanded (Key Commands, Architecture, Testing Strategy, Deployment, Judging Criteria) to match sibling-repo conventions

### Fixed
- `config.Settings` crashed at import — and thus the whole app failed to start — for anyone with ordinary `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` in their environment (pydantic-settings defaults to `extra="forbid"`, and those two vars were never declared fields). Now `extra="ignore"`
- `infra/template.yaml` targeted a Lambda runtime (3.12) that couldn't run this codebase's 3.14-only dependencies

### Removed
- `docs/continuum-DEPLOY.md` — an exact duplicate of `docs/DEPLOY.md`

### Earlier (scaffold)
- Initial project scaffold: README, ARCHITECTURE, ADRs 001–006, SUBMISSION checklist, DEMO_RUNBOOK
- CockroachDB schema: `incidents`, `remediation_steps`, `incident_embeddings` with vector index (`infra/schema.sql`)
- Agent module stubs: orchestrator, correlation, memory, remediation
- Synthetic data generation scripts (stubs)
- Chaos-kill script for resilience demo (stub)
- Hugging Face Spaces deployment: README frontmatter, `.github/workflows/sync-to-hf-space.yml`, `docs/DEPLOY.md` — free, cardless public hosting for the Gradio demo UI, replacing the Railway/Vercel/Next.js stack considered and rejected for this project (no frontend framework needed, judged surface is the CockroachDB memory layer)

## [0.1.0] — scaffold
- Repository initialized for CockroachDB × AWS Hackathon 2026 submission
